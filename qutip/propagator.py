# This file is part of QuTiP: Quantum Toolbox in Python.
#
#    Copyright (c) 2011 and later, Paul D. Nation and Robert J. Johansson.
#    All rights reserved.
#
#    Redistribution and use in source and binary forms, with or without 
#    modification, are permitted provided that the following conditions are 
#    met:
#
#    1. Redistributions of source code must retain the above copyright notice, 
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of the QuTiP: Quantum Toolbox in Python nor the names
#       of its contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
#    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A 
#    PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT 
#    HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
#    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT 
#    LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, 
#    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT 
#    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
#    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

import types
import numpy as np
import scipy.linalg as la
import warnings

from qutip.qobj import Qobj
from qutip.rhs_generate import rhs_clear
from qutip.superoperator import vec2mat, mat2vec
from qutip.mesolve import mesolve
from qutip.sesolve import sesolve
from qutip.essolve import essolve
from qutip.steadystate import steadystate
from qutip.states import basis
from qutip.states import projection
from qutip.odeoptions import Odeoptions


def propagator(H, t, c_op_list, args=None, options=None):
    """
    Calculate the propagator U(t) for the density matrix or wave function such
    that :math:`\psi(t) = U(t)\psi(0)` or
    :math:`\\rho_{\mathrm vec}(t) = U(t) \\rho_{\mathrm vec}(0)`
    where :math:`\\rho_{\mathrm vec}` is the vector representation of the
    density matrix.

    Parameters
    ----------
    H : qobj or list
        Hamiltonian as a Qobj instance of a nested list of Qobjs and
        coefficients in the list-string or list-function format for
        time-dependent Hamiltonians (see description in :func:`qutip.mesolve`).

    t : float or array-like
        Time or list of times for which to evaluate the propagator.

    c_op_list : list
        List of qobj collapse operators.

    args : list/array/dictionary
        Parameters to callback functions for time-dependent Hamiltonians and
        collapse operators.

    options : :class:`qutip.Odeoptions`
        with options for the ODE solver.

    Returns
    -------
     a : qobj
        Instance representing the propagator :math:`U(t)`.

    """

    if options is None:
        options = Odeoptions()
        options.rhs_reuse = True
        rhs_clear()

    tlist = [0, t] if isinstance(t, (int, float, np.int64, np.float64)) else t

    if len(c_op_list) == 0:
        # calculate propagator for the wave function

        if isinstance(H, types.FunctionType):
            H0 = H(0.0, args)
            N = H0.shape[0]
            dims = H0.dims
        elif isinstance(H, list):
            H0 = H[0][0] if isinstance(H[0], list) else H[0]
            N = H0.shape[0]
            dims = H0.dims
        else:
            N = H.shape[0]
            dims = H.dims

        u = np.zeros([N, N, len(tlist)], dtype=complex)

        for n in range(0, N):
            psi0 = basis(N, n)
            output = sesolve(H, psi0, tlist, [], args, options)
            for k, t in enumerate(tlist):
                u[:, n, k] = output.states[k].full().T

        # todo: evolving a batch of wave functions:
        # psi_0_list = [basis(N, n) for n in range(N)]
        # psi_t_list = mesolve(H, psi_0_list, [0, t], [], [], args, options)
        # for n in range(0, N):
        #    u[:,n] = psi_t_list[n][1].full().T

    else:
        # calculate the propagator for the vector representation of the
        # density matrix (a superoperator propagator)

        if isinstance(H, types.FunctionType):
            H0 = H(0.0, args)
            N = H0.shape[0]
            dims = [H0.dims, H0.dims]
        elif isinstance(H, list):
            H0 = H[0][0] if isinstance(H[0], list) else H[0]
            N = H0.shape[0]
            dims = [H0.dims, H0.dims]
        else:
            N = H.shape[0]
            dims = [H.dims, H.dims]

        u = np.zeros([N * N, N * N, len(tlist)], dtype=complex)

        for n in range(0, N * N):
            psi0 = basis(N * N, n)
            rho0 = Qobj(vec2mat(psi0.full()))
            output = mesolve(H, rho0, tlist, c_op_list, [], args, options)
            for k, t in enumerate(tlist):
                u[:, n, k] = mat2vec(output.states[k].full()).T

    if len(tlist) == 2:
        return Qobj(u[:, :, 1], dims=dims)
    else:
        return [Qobj(u[:, :, k], dims=dims) for k in range(len(tlist))]


def _get_min_and_index(lst):
    """
    Private function for obtaining min and max indicies.
    """
    minval, minidx = lst[0], 0
    for i, v in enumerate(lst[1:]):
        if v < minval:
            minval, minidx = v, i + 1
    return minval, minidx


def propagator_steadystate(U):
    """Find the steady state for successive applications of the propagator
    :math:`U`.

    Parameters
    ----------
    U : qobj
        Operator representing the propagator.

    Returns
    -------
    a : qobj
        Instance representing the steady-state density matrix.

    """

    evals, evecs = la.eig(U.full())

    ev_min, ev_idx = _get_min_and_index(abs(evals - 1.0))

    evecs = evecs.T
    rho = Qobj(vec2mat(evecs[ev_idx]), dims=U.dims[0])
    rho = rho * (1.0 / rho.tr())
    rho = 0.5 * (rho + rho.dag())  # make sure rho is herm
    return rho
