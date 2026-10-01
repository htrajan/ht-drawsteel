"""Mailbox transport tests; no running app or model API is needed."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import drawsteel_tools as ds


class ToolTests(unittest.TestCase):
    def test_unknown_command_and_writes_rejected_before_enqueue(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):ds.call("eval",app_data=d)
            with self.assertRaisesRegex(ValueError,"requires --write"):
                ds.call("switch_map",{"id":"yard"},app_data=d)
            with self.assertRaisesRegex(ValueError,"JSON object"):
                ds.call("ping",[],app_data=d)
            self.assertEqual(list(Path(d).iterdir()),[])

    def fake_app(self,root,error=False):
        directory=Path(root)/"compendium/script-tools/requests"
        until=time.monotonic()+2
        while time.monotonic()<until:
            files=list(directory.glob("*.json"))
            if files:
                req=json.loads(files[0].read_text())
                self.assertEqual(req["protocol"],1)
                self.assertEqual(req["game_id"],ds.GAME_ID)
                self.assertGreater(req["expires_ms"],time.time()*1000)
                response={"id":req["id"],"status":"error" if error else "ok"}
                if error:response["error"]="Director mode is required"
                else:response["result"]={"game_id":ds.GAME_ID,"director":True}
                ds.atomic_json(Path(root)/"compendium/script-tools/results"/(req["id"]+".json"),response)
                return
            time.sleep(0.01)
        self.fail("Client never enqueued request")

    def test_structured_response_and_request_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            worker=threading.Thread(target=self.fake_app,args=(d,));worker.start()
            result=ds.call("ping",timeout=2,app_data=d)
            worker.join()
            self.assertTrue(result["director"])
            self.assertEqual(list((Path(d)/"compendium/script-tools/requests").iterdir()),[])

    def test_native_error_propagated(self):
        with tempfile.TemporaryDirectory() as d:
            worker=threading.Thread(target=self.fake_app,args=(d,True));worker.start()
            with self.assertRaisesRegex(RuntimeError,"Director mode"):
                ds.call("ping",timeout=2,app_data=d)
            worker.join()

    def test_timeout_cancels_and_never_retries(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(TimeoutError,"outcome is unknown"):
                ds.call("ping",timeout=0.1,app_data=d)
            root=Path(d)/"compendium/script-tools"
            self.assertEqual(len(list((root/"cancelled").glob("*.json"))),1)
            self.assertEqual(list((root/"requests").glob("*.json")),[])

    def test_engine_table_decoding(self):
        self.assertEqual(ds.decode_lua({"1":{"name":"Vale","_luaTable":True},"_luaTable":False}),[{"name":"Vale"}])
        self.assertEqual(ds.decode_lua({"_luaTable":False}),[])
        self.assertEqual(ds.decode_lua({"__typeName":"NegotiationDocument","_luaTable":True}),{"__typeName":"NegotiationDocument"})


if __name__=="__main__":unittest.main()
