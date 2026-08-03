import unittest
import asyncio
from r_python_bedrock_protocol import Bot, BotConfig, BotCluster

class TestBotCluster(unittest.TestCase):
    def test_cluster_creation(self):
        cluster = BotCluster.create_swarm(
            "127.0.0.1",
            19132,
            names=["AlphaBot", "BetaBot"],
            config_template=BotConfig(version="1.20.80")
        )
        self.assertEqual(len(cluster.bots), 2)
        self.assertEqual(cluster.bots[0].config.username, "AlphaBot")
        self.assertEqual(cluster.bots[1].config.username, "BetaBot")

    def test_add_bot(self):
        cluster = BotCluster()
        bot = Bot("127.0.0.1", 19132, config=BotConfig(username="TestBot"))
        cluster.add_bot(bot)
        self.assertEqual(len(cluster.bots), 1)

if __name__ == '__main__':
    unittest.main()
