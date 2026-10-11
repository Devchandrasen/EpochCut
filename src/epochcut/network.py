"""Four-process authenticated loopback research testbed (HTTP, not MCP).

Computational proposals are untrusted. HTTP adapters, process isolation, local
OS and the authoritative broker are trusted. No real external effects occur.
Bearer transport authentication is loopback-only; WAN/TLS is not claimed.
"""
import argparse
from dataclasses import asdict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from time import perf_counter_ns, sleep
import urllib.request

from .graph import Edge, InfluenceGraph, Node
from .temporal import Broker, Policy, canonical


def network_graph(shortcut=True):
    g = InfluenceGraph()
    for name, kind, cost, eligible in (("planner", "agent", 1, False), ("retriever", "agent", 1, False),
                                      ("executor", "agent", 1, False), ("memory", "memory", 1, False),
                                      ("a", "pep", 1, True), ("b", "queue", 1, False),
                                      ("c", "pep", 2, True), ("t", "pep", 20, True)):
        g.add_node(Node(name, kind, cost, eligible))
    for u, v, interface in (("planner", "retriever", "message"), ("retriever", "executor", "message"),
                            ("memory", "retriever", "memory_read"), ("executor", "a", "tool"),
                            ("a", "b", "queue"), ("b", "c", "callback"), ("c", "t", "effect"),
                            ("executor", "planner", "delegation")):
        g.add_edge(Edge(u, v, interface))
    if shortcut:
        g.add_edge(Edge("executor", "b", "queue"))
    p = Policy("effect", ("planner", "retriever", "executor", "memory"), ("t",), ("a", "c", "t"))
    return g, (p,)


class RPC:
    def __init__(self, role, key):
        self.role, self.key = role, key
        self.lock = threading.Lock()
        self.records = []

    def call(self, url, endpoint, value, timeout=20):
        payload = canonical(value)
        request = urllib.request.Request(url+endpoint, payload, method="POST",
                                         headers={"Content-Type": "application/json", "X-Principal": self.role,
                                                  "Authorization": "Bearer "+self.key})
        start = perf_counter_ns()
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            data = reply.read()
        with self.lock:
            self.records.append({"endpoint": endpoint, "request_body_bytes": len(payload),
                                 "response_body_bytes": len(data), "roundtrip_ns": perf_counter_ns()-start,
                                 "caller": self.role, "peer": url})
        return json.loads(data)


class Service:
    def __init__(self, role, keys, ledger):
        self.role, self.keys = role, keys
        self.rpc = RPC(role, keys[role])
        self.peers = {}
        self.installed = {}
        self.states = {}  # separate process-local workflow state
        self.lock = threading.RLock()
        self.broker = None
        self.barriers = {}
        self.ledger = ledger

    def install(self, cfg):
        body = {"epoch": cfg.epoch, "certificate": cfg.certificate,
                "routes": [asdict(e) for e in sorted(cfg.graph.edges)]}
        acknowledgements = []
        for role in ("planner", "retriever", "executor"):
            reply = self.rpc.call(self.peers[role], "/install", body)
            acknowledgements.append(reply.get("installed") == cfg.epoch)
        self.broker_event_install = {"epoch": cfg.epoch, "acknowledgements": acknowledgements}
        return all(acknowledgements)

    def gc(self):
        epochs = list(self.broker.configs)
        for role in ("planner", "retriever", "executor"):
            self.rpc.call(self.peers[role], "/retain", {"epochs": epochs})

    def control(self, caller, endpoint, body):
        admin = caller == "admin"
        if endpoint == "/health":
            return {"role": self.role, "pid": os.getpid()}
        if endpoint == "/setup" and admin:
            self.peers = body["peers"]
            if self.role == "effect":
                if self.broker:
                    self.broker.close()
                self.broker = Broker(*network_graph(), strategy=body["strategy"], ledger=self.ledger,
                                     max_contexts=128, installer=self.install)
                self.barriers.clear()
            return {"ready": True}
        if self.role != "effect":
            return self.worker(caller, endpoint, body)
        b = self.broker
        if endpoint == "/begin" and admin:
            token = b.begin(body["workflow"], body.get("source", "planner"), body.get("intent"), payload=body.get("payload"))
            return {"token": token, "epoch": b.current}
        if endpoint == "/plan" and caller in {"planner", "retriever", "executor"}:
            with b.lock:
                ctx = b._context(body["token"])
                cfg = b._configuration(ctx)
                path = ["b"] if Edge("executor", "b", "queue") in cfg.graph.edges else ["a", "b"]
                return {"epoch": cfg.epoch, "queue_path": path}
        if endpoint == "/advance" and caller in {"planner", "retriever", "executor"}:
            with b.lock:
                ctx = b._context(body["token"])
                aliases = {"planner": {"planner"}, "retriever": {"retriever"}, "executor": {"executor", "a", "b", "c"}}
                if ctx.node not in aliases[caller]:
                    return {"allowed": False, "reason": "transport_principal_cursor_mismatch"}
                return b.advance(body["token"], body["target"], body["interface"], body["action"], sender=ctx.node)
        if endpoint == "/delegate" and caller == "executor":
            return {"token": b.delegate(body["token"], "planner", body["action"])}
        if endpoint == "/commit" and caller == "executor":
            return b.commit(body["token"], body["action"])
        if endpoint == "/pause" and caller == "executor":
            event = self.barriers.setdefault(body["workflow"], threading.Event())
            event.set()
            b.event("network_queue_barrier", workflow=body["workflow"])
            return {"queued": True}
        if endpoint == "/barrier" and admin:
            event = self.barriers.setdefault(body["workflow"], threading.Event())
            return {"queued": event.wait(body.get("timeout", 10))}
        if endpoint == "/mutate" and admin:
            result = b.admit(*network_graph(body["shortcut"]))
            b.event("network_install_ack", **self.broker_event_install)
            return result
        if endpoint == "/complete" and admin:
            for token in body["tokens"]:
                try:
                    b.finish(token)
                except ValueError:
                    pass
            # A top-level completion cannot leave forgotten causal descendants.
            # The trusted coordinator supplies the workflow, never a model.
            for ctx in list(b.contexts.values()):
                if ctx.credentials["workflow"] == body["workflow"] and ctx.state == "active":
                    b.finish(ctx.token)
            self.gc()
            for role in ("planner", "retriever", "executor"):
                self.rpc.call(self.peers[role], "/forget", {"workflow": body["workflow"]})
            self.barriers.pop(body["workflow"], None)
            return {"done": True}
        if endpoint == "/snapshot" and admin:
            return {"trace": b.trace, "effects": b.effects(), "statistics": b.statistics(),
                    "rpc": self.rpc.records, "graph": b.configs[b.current].graph.canonical_dict()}
        if endpoint == "/statistics" and admin:
            return b.statistics()
        raise ValueError("endpoint_or_principal_not_authorised")

    def worker(self, caller, endpoint, body):
        if endpoint == "/install" and caller == "effect":
            with self.lock:
                self.installed[body["epoch"]] = body
            return {"installed": body["epoch"]}
        if endpoint == "/retain" and caller == "effect":
            with self.lock:
                self.installed = {e: c for e, c in self.installed.items() if e in body["epochs"]}
            return {"retained": sorted(self.installed)}
        if endpoint == "/forget" and caller == "effect":
            with self.lock:
                self.states.pop(body["workflow"], None)
            return {"forgotten": True}
        if endpoint == "/records" and caller == "admin":
            return {"rpc": self.rpc.records, "installed": sorted(self.installed), "state_count": len(self.states)}
        allowed = {"planner": {"admin", "executor"}, "retriever": {"planner"}, "executor": {"admin", "retriever"}}
        if endpoint not in {"/run", "/resume"} or caller not in allowed[self.role]:
            raise ValueError("worker_interface_not_authorised")
        token, workflow = body["token"], body["workflow"]
        action = body["action"]
        if body.get("delay_ms", 0):
            sleep(body["delay_ms"]/1000)  # labelled artificial message delay
        plan = self.rpc.call(self.peers["effect"], "/plan", {"token": token})
        with self.lock:
            if plan["epoch"] not in self.installed:
                return {"allowed": False, "reason": "route_installation_absent"}
            self.states[workflow] = {"token": token, "epoch": plan["epoch"]}
        if self.role in {"planner", "retriever"}:
            target = "retriever" if self.role == "planner" else "executor"
            result = self.rpc.call(self.peers["effect"], "/advance", {"token": token, "target": target, "interface": "message", "action": action})
            if not result["allowed"]:
                return result
            return self.rpc.call(self.peers[target], "/run", body)
        if endpoint == "/run":
            if body.get("nested", 0):
                child = self.rpc.call(self.peers["effect"], "/delegate", {"token": token, "action": action})["token"]
                return self.rpc.call(self.peers["planner"], "/run", {**body, "token": child, "nested": body["nested"]-1})
            for target in plan["queue_path"]:
                result = self.rpc.call(self.peers["effect"], "/advance", {"token": token, "target": target,
                                       "interface": "tool" if target == "a" else "queue", "action": action})
                if not result["allowed"]:
                    return result
            if body.get("pause"):
                self.rpc.call(self.peers["effect"], "/pause", {"workflow": workflow})
                return {"queued": True, "token": token}
        if body.get("undeclared"):
            return self.rpc.call(self.peers["effect"], "/advance", {"token": token, "target": "t", "interface": "unknown", "action": action})
        if not body.get("attempt", True):
            return {"committed": False, "reason": "archived_no_effect_attempt"}
        for target, interface in (("c", "callback"), ("t", "effect")):
            result = self.rpc.call(self.peers["effect"], "/advance", {"token": token, "target": target, "interface": interface, "action": action})
            if not result["allowed"]:
                return result
        return self.rpc.call(self.peers["effect"], "/commit", {"token": token, "action": action})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_):
        pass

    def do_POST(self):
        service = self.server.service
        caller = self.headers.get("X-Principal", "")
        supplied = self.headers.get("Authorization", "")
        valid = caller in service.keys and hmac.compare_digest(supplied, "Bearer "+service.keys[caller])
        status = 200
        try:
            if not valid:
                raise ValueError("transport_authentication_failed")
            length = int(self.headers.get("Content-Length", "0"))
            if length > 65536:
                raise ValueError("oversized_body")
            body = json.loads(self.rfile.read(length))
            result = service.control(caller, self.path, body)
        except Exception as exc:
            status = 403 if not valid else 400
            result = {"error": str(exc)}
        data = canonical(result)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=("planner", "retriever", "executor", "effect"))
    p.add_argument("--ledger", default=":memory:")
    args = p.parse_args()
    keys = json.loads(os.environ["EPOCHCUT_TEST_KEYS"])
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.service = Service(args.role, keys, args.ledger)
    print(json.dumps({"role": args.role, "pid": os.getpid(), "url": f"http://127.0.0.1:{server.server_port}"}), flush=True)
    server.serve_forever()
