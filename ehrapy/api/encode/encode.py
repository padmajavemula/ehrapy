import sys
from typing import List, Optional, Set, Tuple

import numpy as np
from anndata import AnnData
from rich import print
from sklearn.preprocessing import OneHotEncoder

from ehrapy.api.encode._categoricals import _detect_categorical_columns


class Encoder:
    """The main encoder for the initial read AnnData object providing various encoding solutions for
    non numerical or categorical data"""

    available_encode_modes = {"one_hot_encoding"}

    @staticmethod
    def encode(ann_data: AnnData, autodetect=False, categoricals_encode_mode=None) -> AnnData:
        """Encode the inital read AnnData object. Categorical values could be either passed via parameters or autodetected.

        Args:
            ann_data: The inital AnnData object parsed by the :class: Datareader
            autodetect: Autodetection of categorical values (default: False)
            categoricals_encode_mode: Only needed if autodetect set to False. A dict containing the categorical name
            and the encoding mode for the respective column
        """
        # autodetect categorical values, which could lead to more categoricals
        if autodetect:
            ann_data.uns["categoricals"] = _detect_categorical_columns(ann_data.X, ann_data.var_names)
            cat_names = ann_data.uns["categoricals"]["categorical_encoded"]
            Encoder.add_cats_to_obs(ann_data, cat_names)
            Encoder.add_cats_to_uns(ann_data, cat_names)

            encoded_x = None
            encoded_var_names = ann_data.var_names.to_list()

            for categorical in cat_names:
                is_encoded, col_indices = Encoder.check_encode_again(encoded_var_names, categorical)
                encoded_x, encoded_var_names = Encoder.one_hot_encoding(
                    ann_data, encoded_x, encoded_var_names, categorical, is_encoded, col_indices
                )

            # update layer content with the latest categorical encoding and the old other values
            updated_layer = Encoder.update_layer_after_encode(
                ann_data.layers["original"], encoded_x, encoded_var_names, ann_data.var_names.to_list(), cat_names
            )
            encoded_ann_data = AnnData(
                encoded_x,
                obs=ann_data.obs.copy(),
                var=dict(var_names=encoded_var_names),
                layers={"original": updated_layer},
            )

        # user passed categorical values with encoding mode for each
        else:
            ann_data.uns["categoricals_encoded_with_mode"] = categoricals_encode_mode
            cat_encode_mode_keys = categoricals_encode_mode.keys()
            Encoder.add_cats_to_obs(ann_data, cat_encode_mode_keys)
            Encoder.add_cats_to_uns(ann_data, cat_encode_mode_keys)

            encoded_x = None
            encoded_var_names = ann_data.var_names.to_list()

            for categorical in categoricals_encode_mode.keys():
                is_encoded, col_indices = Encoder.check_encode_again(encoded_var_names, categorical)
                mode = categoricals_encode_mode[categorical]
                if mode not in Encoder.available_encode_modes:
                    raise ValueError(
                        f"Please provide one of the available encoding modes for categorical column {categorical}.\n"
                        f"{Encoder.available_encode_modes}"
                    )
                if mode == "one_hot_encoding":
                    encoded_x, encoded_var_names = Encoder.one_hot_encoding(
                        ann_data, encoded_x, encoded_var_names, categorical, is_encoded, col_indices
                    )

            # update original layer content with the new categorical encoding and the old other values
            updated_layer = Encoder.update_layer_after_encode(
                ann_data.layers["original"],
                encoded_x,
                encoded_var_names,
                ann_data.var_names.to_list(),
                cat_encode_mode_keys,
            )

            encoded_ann_data = AnnData(
                encoded_x,
                obs=ann_data.obs.copy(),
                var=dict(var_names=encoded_var_names),
                uns=ann_data.uns.copy(),
                layers={"original": updated_layer},
            )
        del ann_data.obs
        del ann_data.X
        return encoded_ann_data

    @staticmethod
    def one_hot_encoding(
        ann_data: AnnData,
        X: Optional[np.ndarray],  # noqa: N803
        var_names: List[str],
        cat: str,
        is_encoded: bool,
        encoded_indices: Tuple[int, int],
    ) -> Tuple[np.ndarray, List[str]]:
        """Encode categorical column using one hot encoding.

        Args:
            ann_data: The current AnnData object
            X: Current (encoded) X
            var_names: Var names of current AnnData object
            cat: The name of the categorical column to be encoded
            is_encoded: Whether the current categorical is already encoded or not
            encoded_indices: If encoded, the start and end index in var_names for the encoded categorical
        """
        try:
            if not is_encoded:
                idx = var_names.index(cat)
            else:
                idx = [i for i in range(encoded_indices[0], encoded_indices[1])]
        except ValueError:
            print(
                f"[bold red]Could not find column {cat} in AnnData var names. Please check spelling of your "
                f"passed categorical columns!"
            )
            sys.exit(1)
        if X is None:
            if not is_encoded:
                arr = ann_data.X[::, idx : idx + 1]
            else:
                arr = ann_data.uns["original_values_categoricals"][cat]
            x = ann_data.X
        else:
            if not is_encoded:
                arr = X[::, idx : idx + 1]
            else:
                arr = ann_data.uns["original_values_categoricals"][cat]

        enc = OneHotEncoder(handle_unknown="ignore", sparse=False).fit(arr)
        cat_prefixes = [f"ehrapycat_{cat}_{suffix}" for suffix in enc.categories_[0]]
        transformed = enc.transform(arr)
        # delete the original categorical column
        # TODO Maybe we could use resize for inplace deletion
        if X is None:
            del_cat_column_x = np.delete(x, idx, 1)
        else:
            del_cat_column_x = np.delete(X, idx, 1)
        # create the new, encoded X
        temp_x = np.hstack((transformed, del_cat_column_x))
        # delete old categorical name
        if not is_encoded:
            del var_names[idx]
        else:
            del var_names[encoded_indices[0]: encoded_indices[-1]]
        temp_var_names = cat_prefixes + var_names

        return temp_x, temp_var_names

    @staticmethod
    def update_layer_after_encode(
        old_layer: np.ndarray, new_x: np.ndarray, new_var_names: List[str], old_var_names: List[str], cats: List[str]
    ) -> np.ndarray:
        """Update the original layer containing a the initial non categorical values and the latest encoded categorials

        Args:
                old_layer: The previous "oiginal" layer
                new_x: The new encoded X
                new_var_names: The new encoded var names
                old_var_names: The previous var names
                cats: All previous categorical names
        """
        # get the index of the first column of the new encoded X, that does not store an encoded categorical
        new_cat_stop_index = next(i for i in range(len(new_var_names)) if not new_var_names[i].startswith("ehrapycat"))
        # get the index of the first column of the old encoded X, that does not store an encoded categorical
        old_cat_stop_index = next(i for i in range(len(old_var_names)) if not old_var_names[i].startswith("ehrapycat"))
        # keep track of all indices with original value columns, that are (and were) not encoded
        idx_list = []
        for idx, col_name in enumerate(old_var_names[old_cat_stop_index:]):
            # this case is needed, when there are one or more numerical (but categorical) columns, that was not encoded yet
            if col_name not in cats:
                idx_list.append(idx + old_cat_stop_index)
        # slice old original layer using the selector
        old_layer_view = old_layer[:, idx_list]
        # get all encoded categoricals of X
        encoded_cats = new_x[:, :new_cat_stop_index]
        # horizontally stack all encoded categoricals and the remaining "old original values"
        updated_layer = np.hstack((encoded_cats, old_layer_view))
        del old_layer
        return updated_layer

    @staticmethod
    def check_encode_again(var_names: List[str], cat_name: str) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """ """
        # TODO check wheter it's a categorical that needs to be encoded
        # the cat name is in var_names, so it's not encoded yet (encoded categoricals start with 'ehrapycat')
        if cat_name in var_names:
            return False, None
        else:
            start_idx = next(
                (idx for idx, var_name in enumerate(var_names) if var_name.startswith(f"ehrapycat_{cat_name}")), -1
            )
            if start_idx != -1:
                # case: only one encoded column and its the last (and only) one
                if start_idx + 1 >= len(var_names):
                    return True, (start_idx, start_idx + 1)
                # end_idx should point to the first var_name, that does not belong to the current categorical
                end_idx = start_idx + 1
                for i in range(start_idx + 1, len(var_names)):
                    if var_names[i].startswith(f"ehrapycat_{cat_name}"):
                        end_idx += 1
                    else:
                        break
                return True, (start_idx, end_idx)
            else:
                print(f"[bold red]Did not find {cat_name} in variable names. Did you misspelled it?")
                sys.exit(1)

    @staticmethod
    def add_cats_to_obs(ann_data: AnnData, cat_names: Set[str]) -> None:
        """Add the original categorical values to obs.

        Args:
            ann_data: The current AnnData object
            cat_names: Name of each categorical column
        """
        for idx, var_name in enumerate(ann_data.var_names):
            if var_name in ann_data.obs.columns:
                continue
            elif var_name in cat_names:
                ann_data.obs[var_name] = ann_data.X[::, idx : idx + 1]

    @staticmethod
    def add_cats_to_uns(ann_data: AnnData, cat_names: Set[str]) -> None:
        """Add the original categorical values to uns.

        Args:
            ann_data: The current AnnData object
            cat_names: Name of each categorical column
        """
        is_init = "original_values_categoricals" in ann_data.uns.keys()
        ann_data.uns["original_values_categoricals"] = (
            {} if not is_init else ann_data.uns["original_values_categoricals"].copy()
        )

        for idx, var_name in enumerate(ann_data.var_names):
            if is_init and var_name in ann_data.uns["original_values_categoricals"]:
                continue
            elif var_name in cat_names:
                ann_data.uns["original_values_categoricals"][var_name] = ann_data.X[::, idx : idx + 1]
