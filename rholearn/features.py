"""
Generates features vectors for equivariant structural representations.
Currently implemented:
    - lambda-SOAP
"""
import os
import pickle
from typing import List, Optional

import numpy as np

import rascaline
import equistore
from equistore import Labels, TensorMap

from rholearn import io, spherical, utils


def lambda_soap_vector(
    frames: list,
    rascal_hypers: dict,
    neighbor_species: Optional[List[int]] = None,
    even_parity_only: bool = False,
    save_dir: Optional[str] = None,
) -> TensorMap:
    """
    Takes a list of frames of ASE loaded structures and a dict of Rascaline
    hyperparameters and generates a lambda-SOAP (i.e. nu=2) representation of
    the data.

    :param frames: a list of structures generated by the ase.io function.
    :param rascal_hypers: a dict of hyperparameters used to calculate the atom
        density correlation calculated with the Rascaline SphericalExpansion
        calculator.
    :param save_dir: a str of the absolute path to the directory where the
        TensorMap of the calculated lambda-SOAP representation and pickled
        ``rascal_hypers`` dict should be written. If none, the TensorMap will
        not be saved.
    :param neighbor_species: a list of int that correspond to the atomic charges
        of all the neighbour species that you want to be in your properties (or
        features) dimension. This list may contain charges for atoms that don't
        appear in ``frames``, but are included anyway so that the one can
        enforce consistent properties dimension size with other lambda SOAP
        feature vectors.
    :param even_parity_only: a bool that determines whether to only include the
        key/block pairs with even parity under rotation, i.e. sigma = +1.
        Defaults to false, where both parities are included.

    :return: a TensorMap of the lambda-SOAP representation vector of the input
        frames.
    """
    # Create save directory
    if save_dir is not None:
        io.check_or_create_dir(save_dir)

    # Generate Rascaline hypers and Clebsch-Gordon coefficients
    calculator = rascaline.SphericalExpansion(**rascal_hypers)
    cg = spherical.ClebschGordanReal(l_max=rascal_hypers["max_angular"])

    # Generate descriptor via Spherical Expansion
    acdc_nu1 = calculator.compute(frames)

    # nu=1 features
    acdc_nu1 = spherical.acdc_standardize_keys(acdc_nu1)

    # Move "species_neighbor" sparse keys to properties with enforced atom
    # charges if ``neighbor_species`` is specified. This is required as the CG
    # iteration code currently does not handle neighbour species padding
    # automatically.
    keys_to_move = "species_neighbor"
    if neighbor_species is not None:
        keys_to_move = Labels(
            names=(keys_to_move,),
            values=np.array(neighbor_species).reshape(-1, 1),
        )
    acdc_nu1 = acdc_nu1.keys_to_properties(keys_to_move=keys_to_move)

    # Combined nu=1 features to generate nu=2 features. lambda-SOAP is defined
    # as just the nu=2 features.
    acdc_nu2 = spherical.cg_increment(
        acdc_nu1,
        acdc_nu1,
        clebsch_gordan=cg,
        lcut=rascal_hypers["max_angular"],
        other_keys_match=["species_center"],
    )

    # Clean the lambda-SOAP TensorMap. Drop the order_nu key name as this is by
    # definition 2 for all keys.
    acdc_nu2 = utils.drop_key_name(acdc_nu2, key_name="order_nu")

    if even_parity_only:
        # Drop all odd parity keys/blocks
        new_keys = acdc_nu2.keys[acdc_nu2.keys["inversion_sigma"] == +1]
        acdc_nu2 = TensorMap(
            keys=new_keys, blocks=[acdc_nu2[key].copy() for key in new_keys]
        )
        # Drop the inversion_sigma key name as this is now +1 for all
        # keys/blocks
        acdc_nu2 = utils.drop_key_name(acdc_nu2, key_name="inversion_sigma")

    # Write to file
    if save_dir is not None:
        # Rascaline hypers
        with open(os.path.join(save_dir, "rascal_hypers.pickle"), "wb") as handle:
            pickle.dump(rascal_hypers, handle, protocol=pickle.HIGHEST_PROTOCOL)
        # Lambda-SOAP
        eequistore.save(os.path.join(save_dir, "lambda_soap.npz"), acdc_nu2)

    return acdc_nu2


def lambda_soap_kernel(lsoap_vector: TensorMap) -> TensorMap:
    """
    Takes a lambda-SOAP feature vector (as a TensorMap) and takes the relevant
    inner products to form a lambda-SOAP kernel, returned as a TensorMap.
    """
    return
