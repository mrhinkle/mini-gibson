import unittest, json
from pathlib import Path
from src.version import VERSION
class T(unittest.TestCase):
    def test_aligned(self):
        pkg=json.loads(Path('package.json').read_text())
        self.assertEqual(pkg['version'],'1.2.4')
        self.assertEqual(VERSION,'1.2.4')
        self.assertIn('## 1.2.4', Path('CHANGELOG.md').read_text())
if __name__=='__main__': unittest.main()
