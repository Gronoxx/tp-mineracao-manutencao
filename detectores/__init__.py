from . import (
    long_method,
    long_param_list,
    magic_numbers,
    deep_nesting,
    dead_code,
)

DETECTORS = {
    "long_method":     long_method.detect,
    "long_param_list": long_param_list.detect,
    "magic_numbers":   magic_numbers.detect,
    "deep_nesting":    deep_nesting.detect,
    "dead_code":       dead_code.detect,
}