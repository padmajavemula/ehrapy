from typing import Dict, Optional, Tuple, Union

from anndata import AnnData

from ehrapy.api.preprocessing._data_imputation import Imputation


def replace_explicit(
    adata: AnnData,
    replacement: Union[Union[str, int], Dict[str, Union[str, int]], Tuple[str, Union[str, int]]] = None,
    copy: bool = False,
) -> Optional[AnnData]:
    """Replaces all missing values in all or the specified columns with the passed value

    Args:
        adata: :class:`~anndata.AnnData` object containing X to impute values in
        replacement: Replacement value. Can be one of three possible scenarios:
        1. Replace all missing values with the specified value. ( str | int )
        2. Replace all missing values in a subset of columns with the specified value. ( Dict(str: (str, int)) )
        3. Replace all missing values in a subset of columns with a specified value per column. ( str ,(str, int) )
        copy: Whether to return a copy or act inplace

    Returns:
        :class:`~anndata.AnnData` object with imputed X

    Example:
        .. code-block:: python

            import ehrapy.api as ep
            adata = ep.data.mimic_2(encode=True)
            adata_replaced = ep.pp.replace_explicit(adata_3, replacement=0, copy=True)
    """
    return Imputation.explicit(adata, replacement, copy)
