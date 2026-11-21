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

    def test_stars_and_list_markers_pass(self):
        answer = "Themes from 1-2 star reviews:\n1. Late delivery: 4 low-star reviews\n2. Missing item: 1 review"
        self.assertEqual(check_numbers(answer, METRICS, 12), [])

    def test_invented_number_fails(self):
        self.assertEqual(check_numbers("Late deliveries rose to 45% and rating fell by 0.8.", METRICS, 12), [0.8, 45.0])

    def test_count_above_review_count_fails(self):
        self.assertEqual(check_numbers("Late delivery: 30 reviews", METRICS, 12), [30.0])

    def test_small_invented_number_fails(self):
        # a whole number below the review count is only allowed as a count of reviews, not on its own
        self.assertEqual(check_numbers("25% of orders were late.", METRICS, 30), [25.0])
        self.assertEqual(check_numbers("Rating fell to 2 in June.", METRICS, 30), [2.0])


if __name__ == "__main__":
    unittest.main()
