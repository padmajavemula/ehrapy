from typing import Tuple

import numpy as np
import pandas as pd
import pytest
import ehrapy.api as ep
from anndata import AnnData
from pandas import DataFrame
from pandas.testing import assert_frame_equal

from ehrapy.api.anndata_ext import ObsEmptyError, anndata_to_df, df_to_anndata, assert_encoded, NotEncodedError, \
    get_numeric_vars, assert_numeric_vars, set_numeric_vars


class TestAnndataExt:
    def test_df_to_anndata_simple(self):
        df, col1_val, col2_val, col3_val = TestAnndataExt._setup_df_to_anndata()
        expected_x = np.array([col1_val, col2_val, col3_val], dtype="object").transpose()
        adata = df_to_anndata(df)

        assert adata.X.dtype == "object"
        assert adata.X.shape == (100, 3)
        np.testing.assert_array_equal(adata.X, expected_x)

    def test_df_to_anndata_index_column(self):
        df, col1_val, col2_val, col3_val = TestAnndataExt._setup_df_to_anndata()
        expected_x = np.array([col2_val, col3_val], dtype="object").transpose()
        adata = df_to_anndata(df, index_column="col1")

        assert adata.X.dtype == "object"
        assert adata.X.shape == (100, 2)
        np.testing.assert_array_equal(adata.X, expected_x)
        assert list(adata.obs.index) == col1_val

    def test_df_to_anndata_cols_obs_only(self):
        df, col1_val, col2_val, col3_val = TestAnndataExt._setup_df_to_anndata()
        adata = df_to_anndata(df, columns_obs_only=["col1", "col2"])
        assert adata.X.dtype == "float32"
        assert adata.X.shape == (100, 1)
        assert_frame_equal(
            adata.obs, DataFrame({"col1": col1_val, "col2": col2_val}, index=[str(idx) for idx in range(100)])
        )

    def test_df_to_anndata_all_num(self):
        test_array = np.random.randint(0, 100, (4, 5))
        df = DataFrame(test_array, columns=["col" + str(idx) for idx in range(5)])
        adata = df_to_anndata(df)

        assert adata.X.dtype == "float32"
        np.testing.assert_array_equal(test_array, adata.X)

    def test_anndata_to_df_simple(self):
        col1_val, col2_val, col3_val = TestAnndataExt._setup_anndata_to_df()
        expected_df = DataFrame({"col1": col1_val, "col2": col2_val, "col3": col3_val}, dtype="object")
        adata_x = np.array([col1_val, col2_val, col3_val], dtype="object").transpose()
        adata = AnnData(
            X=adata_x,
            obs=DataFrame(index=[idx for idx in range(100)]),
            var=DataFrame(index=["col" + str(idx) for idx in range(1, 4)]),
            dtype="object",
        )
        anndata_df = anndata_to_df(adata)

        assert_frame_equal(anndata_df, expected_df)

    def test_anndata_to_df_all_from_obs(self):
        col1_val, col2_val, col3_val = TestAnndataExt._setup_anndata_to_df()
        expected_df = DataFrame({"col1": col1_val, "col2": col2_val, "col3": col3_val})
        obs = DataFrame({"col2": col2_val, "col3": col3_val})
        adata_x = np.array([col1_val], dtype="object").transpose()
        adata = AnnData(X=adata_x, obs=obs, var=DataFrame(index=["col1"]), dtype="object")
        anndata_df = anndata_to_df(adata, add_from_obs="all")

        assert_frame_equal(anndata_df, expected_df)

    def test_anndata_to_df_some_from_obs(self):
        col1_val, col2_val, col3_val = TestAnndataExt._setup_anndata_to_df()
        expected_df = DataFrame({"col1": col1_val, "col3": col3_val})
        obs = DataFrame({"col2": col2_val, "col3": col3_val})
        adata_x = np.array([col1_val], dtype="object").transpose()
        adata = AnnData(X=adata_x, obs=obs, var=DataFrame(index=["col1"]), dtype="object")
        anndata_df = anndata_to_df(adata, add_from_obs=["col3"])

        assert_frame_equal(anndata_df, expected_df)

    def test_anndata_to_df_throws_error_with_empty_obs(self):
        col1_val = ["patient" + str(idx) for idx in range(100)]
        adata_x = np.array([col1_val], dtype="object").transpose()
        adata = AnnData(
            X=adata_x, obs=DataFrame(index=[idx for idx in range(100)]), var=DataFrame(index=["col1"]), dtype="object"
        )

        with pytest.raises(ObsEmptyError):
            _ = anndata_to_df(adata, add_from_obs=["some_missing_column"])

    @staticmethod
    def _setup_df_to_anndata() -> Tuple[DataFrame, list, list, list]:
        col1_val = ["str" + str(idx) for idx in range(100)]
        col2_val = ["another_str" + str(idx) for idx in range(100)]
        col3_val = [idx for idx in range(100)]
        df = DataFrame({"col1": col1_val, "col2": col2_val, "col3": col3_val})

        return df, col1_val, col2_val, col3_val

    @staticmethod
    def _setup_anndata_to_df() -> Tuple[list, list, list]:
        col1_val = ["patient" + str(idx) for idx in range(100)]
        col2_val = ["feature" + str(idx) for idx in range(100)]
        col3_val = [idx for idx in range(100)]

        return col1_val, col2_val, col3_val

class TestAnnDataUtil:
    def setup_method(self):
        obs_data = {"ID": ["Patient1", "Patient2", "Patient3"], "Age": [31, 94, 62]}

        X_numeric = np.array([[1, 3.4, 2.1, 4], [2, 6.9, 7.6, 2], [1, 4.5, 1.3, 7]], dtype=np.dtype(object))
        var_numeric = {
            "Feature": ["Numeric1", "Numeric2", "Numeric3", "Numeric4"],
            "Type": ["Numeric", "Numeric", "Numeric", "Numeric"],
        }

        X_strings = np.array(
            [
                [1, 3.4, "A string", "A different string"],
                [2, 5.4, "Silly string", "A different string"],
                [2, 5.7, "A string", "What string?"],
            ],
            dtype=np.dtype(object),
        )
        var_strings = {
            "Feature": ["Numeric1", "Numeric2", "String1", "String2"],
            "Type": ["Numeric", "Numeric", "String", "String"],
        }

        self.adata_numeric = AnnData(
            X=X_numeric,
            obs=pd.DataFrame(data=obs_data),
            var=pd.DataFrame(data=var_numeric, index=var_numeric["Feature"]),
            dtype=np.dtype(object),
        )

        self.adata_strings = AnnData(
            X=X_strings,
            obs=pd.DataFrame(data=obs_data),
            var=pd.DataFrame(data=var_strings, index=var_strings["Feature"]),
            dtype=np.dtype(object),
        )

        self.adata_encoded = ep.pp.encode(self.adata_strings.copy(), autodetect=True, encodings={})

    def test_assert_encoded(self):
        """Test for the encoding assertion."""
        assert_encoded(self.adata_encoded)

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            assert_encoded(self.adata_numeric)

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            assert_encoded(self.adata_strings)

    def test_get_numeric_vars(self):
        """Test for the numeric vars getter."""
        vars = get_numeric_vars(self.adata_encoded)
        assert vars == ["Numeric2"]

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            get_numeric_vars(self.adata_numeric)

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            get_numeric_vars(self.adata_strings)

    def test_assert_numeric_vars(self):
        "Test for the numeric vars assertion."
        assert_numeric_vars(self.adata_encoded, ["Numeric2"])

        with pytest.raises(ValueError, match=r"Some selected vars are not numeric"):
            assert_numeric_vars(self.adata_encoded, ["Numeric2", "String1"])

    def test_set_numeric_vars(self):
        """Test for the numeric vars setter."""
        values = np.array(
            [
                [1.2],
                [2.2],
                [2.2],
            ],
            dtype=np.dtype(np.float32),
        )
        adata_set = set_numeric_vars(self.adata_encoded, values, copy=True)
        assert (adata_set.X[:, 3] == values[:, 0]).all()

        with pytest.raises(ValueError, match=r"Some selected vars are not numeric"):
            set_numeric_vars(self.adata_encoded, values, vars=["ehrapycat_String1"])

        string_values = np.array(
            [
                ["A"],
                ["B"],
                ["A"],
            ]
        )

        with pytest.raises(TypeError, match=r"values must be numeric"):
            set_numeric_vars(self.adata_encoded, string_values)

        extra_values = np.array(
            [
                [1.2, 1.3],
                [2.2, 2.3],
                [2.2, 2.3],
            ],
            dtype=np.dtype(np.float32),
        )

        with pytest.raises(ValueError, match=r"does not match number of vars"):
            set_numeric_vars(self.adata_encoded, extra_values)

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            set_numeric_vars(self.adata_numeric, values)

        with pytest.raises(NotEncodedError, match=r"not yet been encoded"):
            set_numeric_vars(self.adata_strings, values)
