import unittest
import config, ui
class T(unittest.TestCase):
    def test_uses_config(self):
        config.THEME='dark'
        # reload behavior: ui should read config.THEME
        import importlib
        importlib.reload(ui)
        self.assertEqual(ui.render(),'theme=dark')
if __name__=='__main__': unittest.main()
