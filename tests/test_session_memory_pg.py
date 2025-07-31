import unittest
from unittest.mock import patch, MagicMock

from services.session_memory import PostgresSessionMemory

class TestPostgresSessionMemory(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor
        patcher = patch('services.session_memory.DatabaseManager.get_connection', return_value=self.mock_conn)
        self.addCleanup(patcher.stop)
        patcher.start()
        self.memory = PostgresSessionMemory(max_turns=10)

    def test_store_turn_trims_history(self):
        self.memory.store_turn('s', 'u', 'b', 'sum')
        # Ensure insert executed
        self.assertTrue(self.mock_cursor.execute.call_count >= 2)
        # Check that deletion query limits to max_turns
        args = self.mock_cursor.execute.call_args_list[-1][0]
        self.assertIn('DELETE FROM session_memory', args[0])
        self.assertEqual(args[1][-1], 10)

    def test_get_history(self):
        self.mock_cursor.fetchall.return_value = [('u1','b1'),('u2','b2')]
        history = self.memory.get_history('s')
        self.assertEqual(len(history), 2)
        self.mock_cursor.execute.assert_called()

    def test_clear(self):
        self.memory.clear('s')
        self.mock_cursor.execute.assert_called_with('DELETE FROM session_memory WHERE session_id = %s', ('s',))

if __name__ == '__main__':
    unittest.main()
