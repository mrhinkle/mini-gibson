"""Parser smoke for inference.smoke. No live model and no environment credentials.

Run: python3 -m unittest tests.evaluation.test_inference_smoke
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import socket
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import inference.smoke as smoke

TOKEN = "hf-secret-value-should-not-appear"
CLAIMED = "operator-claimed-not-observed"


def models(mid="m", **extra):
    return {"data": [{"id": mid, **extra}]}


def completion(model="m", nonce="n", arguments=None, name="gibson_smoke", ident="call-1",
               calls=1, content=None, choices="auto", usage="omit", drop_tools=False):
    if arguments is None:
        arguments = json.dumps({"nonce": nonce})
    call = {"id": ident, "type": "function", "function": {"name": name, "arguments": arguments}}
    tool_calls = calls if isinstance(calls, list) else [call for _ in range(calls)]
    message = {"role": "assistant", "content": content, "tool_calls": tool_calls}
    if drop_tools:
        message.pop("tool_calls")
    body = {"model": model, "choices": [{"message": message}] if choices == "auto" else choices}
    if usage != "omit":
        body["usage"] = usage
    return body


def assert_unscored(test, receipt, mode):
    test.assertFalse(receipt["measured_inference"])
    test.assertFalse(receipt["pins"]["model_revision_verified"])
    test.assertEqual(receipt["score"], "NOT_SCORED")
    test.assertEqual(receipt["stages"], {"full_training": "NO_GO", "tool_conformance": "NO_GO"})
    test.assertEqual(receipt["mode"], mode)
    test.assertNotIn(TOKEN, json.dumps(receipt))
    if mode == "fixture":
        test.assertFalse(receipt["live_inference"])
        test.assertIsNone(receipt["http_success"])


class ValidatorTests(unittest.TestCase):
    def _run(self, comp, models_payload=None, nonce="n"):
        return smoke.run_fixture("m", nonce, models() if models_payload is None else models_payload, comp, CLAIMED)

    def test_valid_tool_call_is_fixture_not_measurement(self):
        comp = completion(content=TOKEN)
        receipt = self._run(comp, models(revision="b3caaabed0263651a17dc1f2d4ce97e794f76c44"))
        assert_unscored(self, receipt, "fixture")
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["nonce_fulfilled"])
        self.assertEqual(receipt["selected_model"], "m")
        self.assertEqual(receipt["response_model"], "m")
        self.assertTrue(receipt["pins"]["observed"]["served_model_present"])
        self.assertEqual(receipt["pins"]["operator_claimed"]["model_revision"], CLAIMED)
        self.assertNotIn("revision", receipt["pins"]["observed"])
        self.assertEqual(receipt["usage_status"], "unavailable")
        self.assertIsNone(receipt["usage"])
        self.assertNotIn("prompt_tokens", json.dumps(receipt))
        raw = smoke.dumps(smoke.build_request("m", "n"))
        self.assertEqual(receipt["request_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(smoke.dumps(comp)).hexdigest())
        request = json.loads(raw)
        self.assertEqual(request["temperature"], 0)
        self.assertEqual(request["tool_choice"]["function"]["name"], "gibson_smoke")
        self.assertEqual(request["tools"][0]["function"]["parameters"]["required"], ["nonce"])

    def test_rejections(self):
        cases = {
            "prose_only": completion(drop_tools=True, content="MINI_GIBSON_OK"),
            "response_model_mismatch": completion(model="other"),
            "unexpected_function": completion(name="other_tool"),
            "nonce_mismatch": completion(nonce="other"),
            "malformed_arguments": completion(arguments="{"),
            "arguments_not_object": completion(arguments="5"),
            "double_json": completion(arguments=json.dumps(json.dumps({"nonce": "n"}))),
            "multiple_calls": completion(calls=2),
            "empty_id": completion(ident=""),
            "empty_choices": completion(choices=[]),
            "null_choices": completion(choices=None),
        }
        codes = {name: name for name in cases}
        codes["double_json"] = "arguments_not_object"
        codes["null_choices"] = "empty_choices"
        for name, comp in cases.items():
            with self.subTest(name=name):
                receipt = self._run(comp)
                assert_unscored(self, receipt, "fixture")
                self.assertFalse(receipt["ok"])
                self.assertFalse(receipt["nonce_fulfilled"])
                self.assertEqual(receipt["error"], codes[name])

    def test_scalar_object_and_bad_usage_are_not_coerced_to_zero(self):
        receipt = self._run(completion(arguments=5))
        self.assertEqual(receipt["error"], "arguments_not_object")
        self.assertIsNone(receipt["usage"])
        bad = self._run(completion(usage={"prompt_tokens": None, "completion_tokens": 1, "total_tokens": 1}))
        self.assertEqual(bad["error"], "bad_usage")
        self.assertIsNone(bad["usage"])
        present = self._run(completion(usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}))
        self.assertTrue(present["ok"])
        self.assertEqual(present["usage"], {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5})

    def test_models_payload(self):
        self.assertEqual(self._run(completion(), {"data": "nope"})["error"], "malformed_models")
        self.assertEqual(self._run(completion(), [])["error"], "malformed_models")
        self.assertEqual(self._run(completion(), {"data": [{"id": ""}]})["error"], "malformed_models")
        self.assertEqual(self._run(completion(), {"data": [{"id": "other"}]})["error"], "model_missing")
        self.assertFalse(self._run(completion(), {"data": [{"id": "other"}]})["pins"]["observed"]["served_model_present"])

    def test_fixture_mode_does_not_open_a_socket(self):
        def explode(*_a, **_k):
            raise AssertionError("network")

        with mock.patch("socket.create_connection", explode), mock.patch.object(urllib.request.OpenerDirector, "open", explode):
            receipt = self._run(completion())
        self.assertTrue(receipt["ok"])
        self.assertFalse(receipt["live_inference"])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._reply(None)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self._reply(raw)

    def _reply(self, raw):
        self.server.hits.append((self.command, self.path, raw, {k: v for k, v in self.headers.items()}))
        code, body = self.server.routes.get(self.path, (404, b""))
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        return


@contextlib.contextmanager
def serve(routes):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.routes = routes
    httpd.hits = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def endpoint(httpd):
    return f"http://127.0.0.1:{httpd.server_address[1]}"


class LiveSeamTests(unittest.TestCase):
    def test_valid_exchange_hashes_and_sends_no_authorization(self):
        comp = completion()
        routes = {"/v1/models": (200, json.dumps(models())), "/v1/chat/completions": (200, json.dumps(comp))}
        with serve(routes) as httpd:
            receipt = smoke.run_live(endpoint(httpd), "m", "n", 2, CLAIMED)
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["live_inference"])
        self.assertFalse(receipt["measured_inference"])
        self.assertTrue(receipt["http_success"])
        self.assertTrue(receipt["nonce_fulfilled"])
        self.assertFalse(receipt["pins"]["model_revision_verified"])
        self.assertEqual(receipt["score"], "NOT_SCORED")
        self.assertEqual(receipt["stages"]["full_training"], "NO_GO")
        post = next(hit for hit in httpd.hits if hit[0] == "POST")
        self.assertNotIn("Authorization", post[3])
        self.assertEqual(receipt["request_sha256"], hashlib.sha256(post[2]).hexdigest())
        self.assertEqual(json.loads(post[2])["tool_choice"]["function"]["name"], "gibson_smoke")
        self.assertNotIn(TOKEN, json.dumps(receipt))

    def test_live_exchange_does_not_discover_proxies(self):
        def explode(*_a, **_k):
            raise AssertionError("proxy discovery")

        comp = completion()
        routes = {"/v1/models": (200, json.dumps(models())), "/v1/chat/completions": (200, json.dumps(comp))}
        with mock.patch("urllib.request.getproxies", side_effect=explode):
            with serve(routes) as httpd:
                receipt = smoke.run_live(endpoint(httpd), "m", "n", 2, CLAIMED)
        assert_unscored(self, receipt, "live")
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["http_success"])
        self.assertTrue(receipt["nonce_fulfilled"])
        self.assertEqual([hit[0] for hit in httpd.hits], ["GET", "POST"])
        self.assertNotIn("Authorization", httpd.hits[1][3])

    def test_http_failures(self):
        comp = json.dumps(completion())
        listed = json.dumps(models())
        cases = {
            "status": {"/v1/models": (503, listed), "/v1/chat/completions": (200, comp)},
            "missing": {"/v1/models": (200, json.dumps(models("other"))), "/v1/chat/completions": (200, comp)},
            "garbage": {"/v1/models": (200, "{"), "/v1/chat/completions": (200, comp)},
            "prose": {"/v1/models": (200, listed), "/v1/chat/completions": (200, json.dumps(completion(drop_tools=True, content="OK")))},
        }
        expect = {"status": "http_status", "missing": "model_missing", "garbage": "bad_json", "prose": "prose_only"}
        for name, routes in cases.items():
            with self.subTest(name=name):
                with serve(routes) as httpd:
                    receipt = smoke.run_live(endpoint(httpd), "m", "n", 2, None)
                self.assertFalse(receipt["ok"])
                self.assertFalse(receipt["measured_inference"])
                self.assertEqual(receipt["error"], expect[name])
                self.assertEqual(receipt["http_success"], name not in {"status", "garbage"})

    def test_timeout_and_connection_failure(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        def hold():
            try:
                conn, _addr = sock.accept()
                time.sleep(2)
                conn.close()
            except OSError:
                return

        threading.Thread(target=hold, daemon=True).start()
        try:
            timed = smoke.run_live(f"http://127.0.0.1:{port}", "m", "n", 0.2, None)
        finally:
            sock.close()
        self.assertEqual(timed["error"], "timed_out")
        self.assertFalse(timed["ok"])
        self.assertFalse(timed["live_inference"])
        self.assertFalse(timed["http_success"])
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        closed_port = closed.getsockname()[1]
        closed.close()
        refused = smoke.run_live(f"http://127.0.0.1:{closed_port}", "m", "n", 1, None)
        self.assertEqual(refused["error"], "connection_failed")
        self.assertFalse(refused["measured_inference"])
        self.assertFalse(refused["live_inference"])

    def test_cli_refuses_implicit_live_and_secrets_and_clobber(self):
        secret_url = "http://user:s3cret@127.0.0.1:9/v1?token=s3cret#s3cret"
        buf = io.StringIO()
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            with contextlib.redirect_stdout(buf):
                code = smoke.main(["--mode", "live", "--model", "m", "--endpoint", secret_url])
        text = buf.getvalue()
        self.assertEqual(code, 2)
        self.assertNotIn("s3cret", text)
        self.assertIn("bad_endpoint", text)
        self.assertIn('"measured_inference": false', text)
        with tempfile_pair() as (models_path, comp_path, out_path):
            argv = ["--model", "m", "--nonce", "n", "--fixture-models", models_path,
                    "--fixture-completion", comp_path, "--output", out_path, "--claimed-revision", CLAIMED]
            with mock.patch.dict(os.environ, {"HF_TOKEN": TOKEN}), mock.patch("socket.create_connection", side_effect=AssertionError("network")):
                self.assertEqual(smoke.main(argv), 0)
                first = out_path_read(out_path)
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    again = smoke.main(argv)
            self.assertEqual(again, 2)
            self.assertEqual(out_path_read(out_path), first)
            self.assertIn("output_exists", buf2.getvalue())
            self.assertNotIn(TOKEN, first)
            self.assertNotIn(TOKEN, buf2.getvalue())

    def test_malformed_port_cli_returns_receipt(self):
        urls = (
            "http://127.0.0.1:not-a-port",
            "http://127.0.0.1:65536",
            "http://127.0.0.1:-1",
            "http://[::1]:99999",
        )
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(smoke.SmokeError) as caught:
                    smoke.endpoint_origin(url)
                self.assertEqual(caught.exception.code, "bad_endpoint")
                self.assertNotIn(url, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)
                out, err = io.StringIO(), io.StringIO()
                with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        code = smoke.main(["--mode", "live", "--model", "m", "--endpoint", url])
                text, err_text = out.getvalue(), err.getvalue()
                self.assertEqual(code, 2)
                self.assertEqual(err_text, "")
                self.assertNotIn("Traceback", text)
                self.assertNotIn("ValueError", text)
                self.assertNotIn(url, text)
                receipt = json.loads(text)
                assert_unscored(self, receipt, "live")
                self.assertFalse(receipt["ok"])
                self.assertFalse(receipt["live_inference"])
                self.assertFalse(receipt["http_success"])
                self.assertEqual(receipt["error"], "bad_endpoint")


@contextlib.contextmanager
def tempfile_pair():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        models_path = root / "models.json"
        comp_path = root / "completion.json"
        out_path = root / "receipt.json"
        models_path.write_text(json.dumps(models()))
        comp_path.write_text(json.dumps(completion(content=TOKEN)))
        yield str(models_path), str(comp_path), str(out_path)


def out_path_read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


if __name__ == "__main__":
    unittest.main()
