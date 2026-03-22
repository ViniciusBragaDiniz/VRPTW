"""Tests for vrptw.postprocessing — partition generation."""

from vrptw.postprocessing import generate_partitions


class TestGeneratePartitions:
    def test_single_element(self):
        result = generate_partitions([1])
        assert result == [[[1]]]

    def test_two_elements_count(self):
        result = generate_partitions([1, 2])
        assert len(result) == 2  # Bell(2) = 2

    def test_two_elements_coverage(self):
        result = generate_partitions([1, 2])
        for partition in result:
            flat = sorted(x for subset in partition for x in subset)
            assert flat == [1, 2]

    def test_three_elements_bell_number(self):
        result = generate_partitions([1, 2, 3])
        assert len(result) == 5  # Bell(3) = 5

    def test_contains_single_subset(self):
        result = generate_partitions([1, 2, 3])
        single = [p for p in result if len(p) == 1]
        assert len(single) == 1
        assert sorted(single[0][0]) == [1, 2, 3]

    def test_contains_all_singletons(self):
        result = generate_partitions([1, 2, 3])
        singletons = [p for p in result if all(len(s) == 1 for s in p)]
        assert len(singletons) == 1

    def test_four_elements_bell_number(self):
        result = generate_partitions([1, 2, 3, 4])
        assert len(result) == 15  # Bell(4) = 15

    def test_partitions_are_disjoint_and_complete(self):
        elements = [10, 20, 30]
        for partition in generate_partitions(elements):
            flat = [x for subset in partition for x in subset]
            assert sorted(flat) == sorted(elements)
            assert len(flat) == len(elements)
