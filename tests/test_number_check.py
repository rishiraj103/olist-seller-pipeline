import unittest

from genai.insights import check_numbers

METRICS = [{"scope": "seller", "month": "2018-03", "orders": 41, "late_pct": 26.83,
            "avg_delay_vs_estimate_days": -3.5, "avg_rating": 3.12}]


class TestNumberCheck(unittest.TestCase):
    def test_traceable_numbers_pass(self):
        answer = "In 2018-03 the rating was 3.12 (about 3.1) and 26.8% of 41 orders were late, 3.5 days early on average."
        self.assertEqual(check_numbers(answer, METRICS, review_count=12), [])

    def test_theme_counts_up_to_review_count_pass(self):
        self.assertEqual(check_numbers("1) Late delivery: 7 reviews 2) Wrong item: 12 reviews", METRICS, 12), [])

    def test_invented_number_fails(self):
        self.assertEqual(check_numbers("Late deliveries rose to 45% and rating fell by 0.8.", METRICS, 12), [0.8, 45.0])

    def test_count_above_review_count_fails(self):
        self.assertEqual(check_numbers("Late delivery: 30 reviews", METRICS, 12), [30.0])


if __name__ == "__main__":
    unittest.main()
