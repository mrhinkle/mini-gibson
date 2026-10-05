import unittest
from retry import retry_call
class T(unittest.TestCase):
    def test_retries(self):
        state={'n':0}
        def flaky():
            state['n']+=1
            if state['n']<3: raise ValueError('fail')
            return 'ok'
        self.assertEqual(retry_call(flaky, times=3),'ok')
        self.assertEqual(state['n'],3)
if __name__=='__main__': unittest.main()
