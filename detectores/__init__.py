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

# Limiares default por detector parametrizável (R1/R2/R4). Usado por
# ferramentas que varrem thresholds (p.ex. o estudo de calibração no
# repo do dataset). `magic_numbers` e `dead_code` não são parametrizados.
DETECTOR_DEFAULT_PARAMS = {
    "long_method":     long_method.DEFAULT_PARAMS,
    "long_param_list": long_param_list.DEFAULT_PARAMS,
    "deep_nesting":    deep_nesting.DEFAULT_PARAMS,
}