"""Offline regression checks for the scoped Steam campaign import."""
import copy
import sqlite3
import unittest

import integrate_session3 as s3


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE stores(name TEXT PRIMARY KEY,value BLOB)")
        for cid in [hero["id"] for hero in s3.sync.HEROES.values()]:
            s3.write_store(self.db,"game::characters/"+cid,{
                "properties":{"damage_taken":17,"victories":3,"resources":{"main":1},"marker":"preserve"},
                "locInfo":{"updateid":2147483648,"loc":{"0":2,"1":0,"2":3}},
            })
        s3.write_store(self.db,"mapdetails:"+s3.sync.LIFT_YARD_MAP_ID+"::root",{
            "floors":{s3.sync.LIFT_YARD_FLOOR_ID:s3.sync.empty_floor(None,"Yard",None)}})
        self.writes, self.copies, self.records=s3.prepare(self.db)

    def tearDown(self):
        self.db.close()

    def test_script_and_privacy(self):
        docs=self.writes["game::assets/objectTables"]["documents"]["table"]
        script=docs[s3.sync.document_record(s3.SESSION,0)[0]]
        self.assertEqual(script["content"],s3.SESSION.read_text())
        self.assertTrue(all(d["hiddenFromPlayers"] for d in docs.values()))
        cipher=docs[s3.SID("session3:document:cipher")]["content"]
        self.assertIn("WKLUG OHGJHU OLIW BDUG",cipher)
        self.assertNotIn("THIRD LEDGER LIFT YARD",cipher)
        self.assertNotIn("THE BOOK IS SAFE",docs[s3.SID("session3:document:reply")]["content"])

    def test_negotiation(self):
        doc=self.writes["game::assets/objectTables"]["documents"]["table"][s3.NEGOTIATION]
        self.assertEqual((doc["startInterest"],doc["startPatience"],doc["impression"]),(2,3,3))
        self.assertEqual([doc["traits"][str(i)]["name"] for i in range(1,5)],
                         ["Protection","Power","Greed","Justice"])
        self.assertIn("will appear",doc["offers"]["4"]["terms"])
        for i in range(1,7):self.assertIn("complete confession",doc["offers"][str(i)]["terms"])

    def test_native_profiles_and_squads(self):
        bestiary=self.writes["game::assets/monsters"]
        vale=bestiary[self.records["irena-vale"]]["info"]["properties"]
        self.assertEqual((vale["cr"],vale["ev"],vale["max_hitpoints"],vale["walkingSpeed"],vale["stability"]),(4,20,100,5,1))
        self.assertEqual(vale["innateActivatedAbilities"]["1"]["behaviors"]["1"]["tiers"]["3"],"14 damage; slide 3; A<2 slowed (EoT)")
        reactions=[v for k,v in vale["characterFeatures"].items() if k!="_luaTable" and v["name"]=="Change Places"]
        self.assertEqual(reactions[0]["modifiers"]["1"]["behavior"],"powertabletrigger")
        self.assertTrue(reactions[0]["modifiers"]["1"]["powerRollModifier"]["changeTarget"])
        chars=[v for k,v in self.writes.items() if k.startswith("game::characters/") and v["properties"].get("groupid")==s3.GROUP]
        minions=[c for c in chars if c["properties"]["minion"]]
        self.assertEqual(len(minions),8)
        self.assertEqual(sorted([sum(c["properties"]["minionSquad"]==q for c in minions) for q in {c["properties"]["minionSquad"] for c in minions}]),[4,4])
        self.assertEqual(len({c["properties"].get("initiativeGrouping") for c in chars if c["properties"].get("initiativeGrouping")}),3)

    def test_hero_preservation_and_reapply(self):
        for hero in s3.sync.HEROES.values():
            key="game::characters/"+hero["id"]
            self.assertEqual(self.writes[key]["properties"],s3.read_store(self.db,key)["properties"])
            self.assertEqual(self.writes[key]["locInfo"]["updateid"],1)
        for k,v in self.writes.items():s3.write_store(self.db,k,v)
        key="game::characters/"+s3.FENWICK
        current=s3.read_store(self.db,key)
        current["properties"]["damage_taken"]=7
        current["locInfo"]["loc"]=[7,-6,0]
        s3.write_store(self.db,key,current)
        again,_,_=s3.prepare(self.db)
        self.assertEqual(again[key]["properties"]["damage_taken"],7)
        self.assertEqual(again[key]["locInfo"],current["locInfo"])

    def test_native_position_order_and_migration(self):
        self.assertEqual(s3.loc("L8"),[2,-1,0])
        self.assertEqual(s3.loc("J4",2),[0,3,2])
        key="game::characters/"+s3.FENWICK
        old=copy.deepcopy(self.writes[key])
        del old["properties"]["session3PlacementVersion"]
        old["locInfo"]["loc"]={"0":1,"1":0,"2":-1}
        s3.write_store(self.db,key,old)
        again,_,_=s3.prepare(self.db)
        self.assertEqual(again[key]["locInfo"]["loc"],[1,-1,0])
        for hero in s3.sync.HEROES.values():
            self.assertEqual(self.writes["game::characters/"+hero["id"]]["locInfo"]["loc"],[2,0,3])

    def test_registered_office_and_assets(self):
        self.assertIn("game::mapManifests/"+s3.OFFICE_MAP,self.writes)
        self.assertIn("maps:"+s3.OFFICE_MAP+"::root",self.writes)
        self.assertEqual(len(self.copies),6)
        self.assertTrue(all(source.exists() for source,_ in self.copies))


if __name__=="__main__":unittest.main()
