"""持久化层共享常量。"""

CSV_ENCODING_UTF8_SIG = "utf-8-sig"
METADATA_JSON_FILENAME = "metadata.json"
DATA_NPZ_FILENAME = "data.npz"
DEFAULT_SET_H5_FILENAME = "samples.h5"
METADATA_TABLE_FILENAME = "metadata.csv"

# metadata.csv schema
META_COL_UID = "_uid"
META_COL_NAME = "_name"
META_COL_ALIAS = "_alias"
META_COL_METADATA_JSON = "_metadata_json"
METADATA_TABLE_COLUMNS = [
    META_COL_UID,
    META_COL_NAME,
    META_COL_ALIAS,
    META_COL_METADATA_JSON,
]

# H5 attrs schema
H5_ATTR_UID = "uid"
H5_ATTR_ALIAS = "alias"
H5_ATTR_METADATA_JSON = "metadata_json"
H5_ATTR_UNIT = "unit"

# data options
DATA_OPTION_ATTR_DATA_FORMAT = "attr_data_format"
DATA_OPTION_DECIMAL_ROUND = "decimal_round"
DATA_OPTION_FLOAT_DTYPE = "float_dtype"
