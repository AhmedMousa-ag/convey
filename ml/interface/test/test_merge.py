import unittest
import numpy as np
from unittest.mock import MagicMock, patch
import copy
from ..merge import IGreedySoup


class TestIGreedySoup(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock the IStrategy parent class
        self.mock_strategy = MagicMock()

        # Create a mock IGreedySoup instance with initial weights
        self.initial_weights = {
            "layer1": np.array([1.0, 2.0, 3.0]),
            "layer2": np.array([4.0, 5.0, 6.0]),
        }

        # Assuming IGreedySoup inherits from IStrategy
        with patch.object(IGreedySoup, "merge"):
            self.greedy_soup = IGreedySoup(
                "test_model_greedy_soup", weights=self.initial_weights
            )
            self.greedy_soup.model_weights = copy.deepcopy(self.initial_weights)

    def test_merge_first_update(self):
        """Test merge with first new weights (count becomes 2.0)."""
        new_weights = {
            "layer1": np.array([2.0, 3.0, 4.0]),
            "layer2": np.array([5.0, 6.0, 7.0]),
        }

        result = self.greedy_soup.merge(new_weights)

        # Expected: old + (new - old) / 2
        expected_layer1 = np.array([1.5, 2.5, 3.5])
        expected_layer2 = np.array([4.5, 5.5, 6.5])

        np.testing.assert_array_almost_equal(result["layer1"], expected_layer1)
        np.testing.assert_array_almost_equal(result["layer2"], expected_layer2)
        self.assertEqual(self.greedy_soup.count, 2.0)

    def test_merge_multiple_updates(self):
        """Test merge with multiple consecutive updates."""
        # First update
        new_weights_1 = {
            "layer1": np.array([2.0, 3.0, 4.0]),
            "layer2": np.array([5.0, 6.0, 7.0]),
        }
        self.greedy_soup.merge(new_weights_1)

        # Second update
        new_weights_2 = {
            "layer1": np.array([3.0, 4.0, 5.0]),
            "layer2": np.array([6.0, 7.0, 8.0]),
        }
        result = self.greedy_soup.merge(new_weights_2)

        # After first merge: [1.5, 2.5, 3.5]
        # After second merge: [1.5, 2.5, 3.5] + ([3.0, 4.0, 5.0] - [1.5, 2.5, 3.5]) / 3
        expected_layer1 = np.array([2.0, 3.0, 4.0])

        np.testing.assert_array_almost_equal(result["layer1"], expected_layer1)
        self.assertEqual(self.greedy_soup.count, 3.0)


if __name__ == "__main__":
    unittest.main()
