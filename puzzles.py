import argparse
from typing import List
import os

import torch
import triton
import triton.language as tl

# Local imports
from display import print_end_line
from tensor_type import Float32, Int32
from test_puzzle import test


"""
# Triton Puzzles Lite

Programming for accelerators such as GPUs is critical for modern AI systems.
This often means programming directly in proprietary low-level languages such as CUDA. Triton is 
an alternative open-source language that allows you to code at a higher-level and compile to accelerators 
like GPU.

Coding for Triton is very similar to Numpy and PyTorch in both syntax and semantics. However, as a lower-level 
language there are a lot of details that you need to keep track of. In particular, one area that learners have 
trouble with is memory loading and storage which is critical for speed on low-level devices.

This set is puzzles is meant to teach you how to use Triton from first principles in an interactive fashion. 
You will start with trivial examples and build your way up to real algorithms like Flash Attention and 
Quantized neural networks. These puzzles **do not** need to run on GPU since they use a Triton interpreter.
"""


r"""
## Introduction

To begin with, we will only use `tl.load` and `tl.store` in order to build simple programs.
"""


"""
### Demo 1

Here's an example of load. It takes an `arange` over the memory. By default the indexing of
torch tensors with column, rows, depths or right-to-left. It also takes in a mask as the second
argument. Mask is critically important because all shapes in Triton need to be powers of two.

Expected Results:

[0 1 2 3 4 5 6 7]
[1. 1. 1. 1. 1. 0. 0. 0.]

Explanation:

tl.load(ptr, mask)
tl.load use mask: [0 1 2 3 4 5 6 7] < 5 = [1 1 1 1 1 0 0 0]
"""


@triton.jit
def demo1(x_ptr):
    range = tl.arange(0, 8)
    # print works in the interpreter
    print(range)
    x = tl.load(x_ptr + range, range < 5, 0)
    print(x)


def run_demo1():
    print("Demo1 Output: ")
    demo1[(1, 1, 1)](torch.ones(4, 3))
    print_end_line()


"""
### Demo 2:

You can also use this trick to read in a 2d array.

Expected Results:

[[ 0  1  2  3]
[ 4  5  6  7]
[ 8  9 10 11]
[12 13 14 15]
[16 17 18 19]
[20 21 22 23]
[24 25 26 27]
[28 29 30 31]]
[[1. 1. 1. 0.]
[1. 1. 1. 0.]
[1. 1. 1. 0.]
[1. 1. 1. 0.]
[0. 0. 0. 0.]
[0. 0. 0. 0.]
[0. 0. 0. 0.]
[0. 0. 0. 0.]]

Explanation:

tl.load use mask: i < 4 and j < 3.
"""


@triton.jit
def demo2(x_ptr):
    i_range = tl.arange(0, 8)[:, None]
    j_range = tl.arange(0, 4)[None, :]
    range = i_range * 4 + j_range
    # print works in the interpreter
    print(range)
    x = tl.load(x_ptr + range, (i_range < 4) & (j_range < 3), 0)
    print(x)


def run_demo2():
    print("Demo2 Output: ")
    demo2[(1, 1, 1)](torch.ones(4, 4))
    print_end_line()


"""
### Demo 3

The `tl.store` function is quite similar. It allows you to write to a tensor.

Expected Results:

tensor([[10., 10., 10.],
    [10., 10.,  1.],
    [ 1.,  1.,  1.],
    [ 1.,  1.,  1.]])

Explanation:

tl.store(ptr, value, mask)
here range < 5 corresponds to the 2D-mask

[[1. 1. 1.]
[1. 1. 0.]
[0. 0. 0.]
[0. 0. 0.]]
"""


@triton.jit
def demo3(z_ptr):
    range = tl.arange(0, 8)
    z = tl.store(z_ptr + range, 10, range < 5)


def run_demo3():
    print("Demo3 Output: ")
    z = torch.ones(4, 3)
    demo3[(1, 1, 1)](z)
    print(z)
    print_end_line()


"""
### Demo 4

You can only load in relatively small `blocks` at a time in Triton. To work 
with larger tensors you need to use a program id axis to run multiple blocks in 
parallel. 

Here is an example with one program axis with 3 blocks.

Expected Results:

Print for each [0] [1. 1. 1. 1. 1. 1. 1. 1.]
Print for each [1] [1. 1. 1. 1. 1. 1. 1. 1.]
Print for each [2] [1. 1. 1. 1. 0. 0. 0. 0.]

Explanation:

This program launch 3 blocks in parallel. For each block (pid=0, 1, 2), it loads 8 
elements. Note that similar to demo3, multi-dimensional tensors are flattened when we 
use pointer (i.e. continuous in memory).
"""


@triton.jit
def demo4(x_ptr):
    pid = tl.program_id(0)
    range = tl.arange(0, 8) + pid * 8
    x = tl.load(x_ptr + range, range < 20)
    print("Print for each", pid, x)


def run_demo4():
    print("Demo4 Output: ")
    x = torch.ones(2, 4, 4)
    demo4[(3, 1, 1)](x)
    print_end_line()


r"""
## Puzzle 1: Constant Add

Add a constant to a vector. Uses one program id axis. 
Block size `B0` is always the same as vector `x` with length `N0`.

.. math::
    z_i = 10 + x_i \text{ for } i = 1\ldots N_0
"""


def add_spec(x: Float32[32,]) -> Float32[32,]:
    "This is the spec that you should implement. Uses typing to define sizes."
    return x + 10.0


@triton.jit
def add_kernel(x_ptr, z_ptr, N0, B0: tl.constexpr):
    # We name the offsets of the pointers as "off_"
    off_x = tl.arange(0, B0)
    x = tl.load(x_ptr + off_x)
    x = x + 10.0
    tl.store(z_ptr + off_x, x)
    # Finish me!
    return


r"""
## Puzzle 2: Constant Add Block

Add a constant to a vector. Uses one program block axis (no `for` loops yet). 
Block size `B0` is now smaller than the shape vector `x` which is `N0`.

.. math::
    z_i = 10 + x_i \text{ for } i = 1\ldots N_0
"""


def add2_spec(x: Float32[200,]) -> Float32[200,]:
    return x + 10.0


@triton.jit
def add_mask2_kernel(x_ptr, z_ptr, N0, B0: tl.constexpr):
    # Finish me!
    pid = tl.program_id(axis = 0)
    block_start = pid * B0
    offsets = block_start + tl.arange(0, B0)
    mask = offsets < N0
    x = tl.load(x_ptr + offsets, mask = mask)
    x += 10
    tl.store(z_ptr + offsets, x, mask = mask)
    return


r"""
## Puzzle 3: Outer Vector Add

Add two vectors.

Uses one program block axis. Block size `B0` is always the same as vector `x` length `N0`.
Block size `B1` is always the same as vector `y` length `N1`.

.. math::
    z_{j, i} = x_i + y_j\text{ for } i = 1\ldots B_0,\ j = 1\ldots B_1
"""


def add_vec_spec(x: Float32[32,], y: Float32[32,]) -> Float32[32, 32]:
    return x[None, :] + y[:, None]


@triton.jit
def add_vec_kernel(x_ptr, y_ptr, z_ptr, N0, N1, B0: tl.constexpr, B1: tl.constexpr):
    # Finish me!
    # B1行，B1列
    off_x = tl.arange(0, B0)
    off_y = tl.arange(0, B1)
    off_z = off_y[:, None] * B1 + off_x[None, :]
    
    x = tl.load(x_ptr + off_x)
    y = tl.load(y_ptr + off_y)
    
    z = x[None, :] + y[:, None]
    tl.store(z_ptr + off_z, z)
    
    return


r"""
## Puzzle 4: Outer Vector Add Block

Add a row vector to a column vector.

Uses two program block axes. Block size `B0` is always less than the vector `x` length `N0`.
Block size `B1` is always less than vector `y` length `N1`.

.. math::
    z_{j, i} = x_i + y_j\text{ for } i = 1\ldots N_0,\ j = 1\ldots N_1
"""


def add_vec_block_spec(x: Float32[100,], y: Float32[90,]) -> Float32[90, 100]:
    return x[None, :] + y[:, None]


@triton.jit
def add_vec_block_kernel(
    x_ptr, y_ptr, z_ptr, N0, N1, B0: tl.constexpr, B1: tl.constexpr
):
    block_id_x = tl.program_id(0)
    block_id_y = tl.program_id(1)
    
    start_x = block_id_x * B0
    start_y = block_id_y * B1
    
    off_x = start_x + tl.arange(0, B0)
    mask_x = off_x < N0
    off_y = start_y + tl.arange(0, B1)
    mask_y = off_y < N1
    
    x = tl.load(x_ptr + off_x, mask=mask_x)
    y = tl.load(y_ptr + off_y, mask=mask_y)
    z = x[None, :] + y[:, None]
    
    # lock_size_x = tl.num_programs(0)
    # block_size_y = tl.num_programs(1)
    
    # start_z = block_id_y * block_size_x * B0 + block_size_y 
    off_z = off_y[:, None] * N0 + off_x[None, :]
    mask_z = mask_y[:, None] & mask_x[None, :]
    
    tl.store(z_ptr + off_z, z, mask=mask_z)    
    # Finish me!
    return


r"""
## Puzzle 5: Fused Outer Multiplication

Multiply a row vector to a column vector and take a relu.

Uses two program block axes. Block size `B0` is always less than the vector `x` length `N0`.
Block size `B1` is always less than vector `y` length `N1`.

.. math::
    z_{j, i} = \text{relu}(x_i \times y_j)\text{ for } i = 1\ldots N_0,\ j = 1\ldots N_1
"""


def mul_relu_block_spec(x: Float32[100,], y: Float32[90,]) -> Float32[90, 100]:
    return torch.relu(x[None, :] * y[:, None])


@triton.jit
def mul_relu_block_kernel(
    x_ptr, y_ptr, z_ptr, N0, N1, B0: tl.constexpr, B1: tl.constexpr
):
    block_id_x = tl.program_id(0)
    block_id_y = tl.program_id(1)
    
    off_x = block_id_x * B0 + tl.arange(0, B0)
    off_y = block_id_y * B1 + tl.arange(0, B1)
    
    mask_x = off_x < N0
    mask_y = off_y < N1
    
    x = tl.load(x_ptr + off_x, mask=mask_x)
    y = tl.load(y_ptr + off_y, mask=mask_y)
    
    z = x[None, :] * y[:, None]
    off_z = off_x[None, :] + off_y[:, None] * N0
    mask_z = mask_x[None, :] & mask_y[:, None]
    
    z = tl.where(z > 0, z, 0)
    tl.store(z_ptr + off_z, z, mask=mask_z)
    # Finish me!
    return


r"""
## Puzzle 6: Fused Outer Multiplication - Backwards

Backwards of a function that multiplies a matrix with a row vector and take a relu.

Uses two program blocks. Block size `B0` is always less than the vector `x` length `N0`.
Block size `B1` is always less than vector `y` length `N1`. Chain rule backward `dz`
is of shape `N1` by `N0`

.. math::
    f(x, y) = \text{relu}(x_{j, i} \times y_j)\text{ for } i = 1\ldots N_0,\ j = 1\ldots N_1

.. math::
    dx_{j, i} = f_x'(x, y)_{j, i} \times dz_{j, i}
"""


def mul_relu_block_back_spec(
    x: Float32[90, 100], y: Float32[90,], dz: Float32[90, 100]
) -> Float32[90, 100]:
    x = x.clone()
    y = y.clone()
    x = x.requires_grad_(True)
    y = y.requires_grad_(True)
    z = torch.relu(x * y[:, None])
    z.backward(dz)
    dx = x.grad
    return dx


@triton.jit
def mul_relu_block_back_kernel(
    x_ptr, y_ptr, dz_ptr, dx_ptr, N0, N1, B0: tl.constexpr, B1: tl.constexpr
):
    block_id_i = tl.program_id(0)
    block_id_j = tl.program_id(1)
    # Finish me!
    
    off_i = block_id_i * B0 + tl.arange(0, B0)
    off_j = block_id_j * B1 + tl.arange(0, B1)
    off_ji = off_j[:, None] * N0 + off_i[None, :]
    
    mask_i = off_i < N0
    mask_j = off_j < N1
    mask_ji = mask_j[:, None] & mask_i[None, :]
    
    x = tl.load(x_ptr + off_ji, mask_ji)
    y = tl.load(y_ptr + off_j, mask_j)
    dz = tl.load(dz_ptr + off_ji, mask_ji)
     
    f = y[:, None] * x
    df = tl.where(f > 0, 1.0, 0.0)
    dx = y[:, None] * df * dz
         
    
    tl.store(dx_ptr + off_ji, dx, mask=mask_ji)
    return


r"""
## Puzzle 7: Long Sum

Sum of a batch of numbers.

Uses one program blocks. Block size `B0` represents a range of batches of  `x` of length `N0`.
Each element is of length `T`. Process it `B1 < T` elements at a time.  

.. math::
    z_{i} = \sum^{T}_j x_{i,j} =  \text{ for } i = 1\ldots N_0

Hint: You will need a for loop for this problem. These work and look the same as in Python.
"""


def sum_spec(x: Float32[4, 200]) -> Float32[4,]:
    return x.sum(1)


@triton.jit
def sum_kernel(x_ptr, z_ptr, N0, N1, T, B0: tl.constexpr, B1: tl.constexpr):
    # Finish me!
    block_id = tl.program_id(0)
    off_i = block_id * B0 + tl.arange(0, B0)
    mask_i = off_i < N0
    z = tl.zeros([B0], dtype = tl.float32)
    
    for id_j in tl.range(0, T, B1):
        off_j = id_j + tl.arange(0, B1)
        mask_j = off_j < T
        off_ij = off_i[:, None] * T + off_j[None, :]
        mask_ij = mask_i[:, None] & mask_j[None, :]
        x = tl.load(x_ptr + off_ij, mask=mask_ij)
        z += tl.sum(x, axis = 1)
        
    tl.store(z_ptr + off_i, z)    
    
    return


r"""
## Puzzle 8: Long Softmax

Softmax of a batch of logits.

Uses one program block axis. Block size `B0` represents the batch of `x` of length `N0`.
Block logit length `T`.   Process it `B1 < T` elements at a time.  

.. math::
    z_{i, j} = \text{softmax}(x_{i,1} \ldots x_{i, T}) \text{ for } i = 1\ldots N_0

Note softmax needs to be computed in numerically stable form as in Python. In addition in Triton 
they recommend not using `exp` but instead using `exp2`. You need the identity

.. math::
    \exp(x) = 2^{\log_2(e) x}

Advanced: there one way to do this with 3 loops. You can also do it with 2 loops if you are clever. 
Hint: you will find this identity useful:

.. math::
    \exp(x_i - m) =  \exp(x_i - m/2 - m/2) = \exp(x_i - m/ 2) /  \exp(m/2)
"""


def softmax_spec(x: Float32[4, 200]) -> Float32[4, 200]:
    x_max = x.max(1, keepdim=True)[0]
    x = x - x_max
    x_exp = x.exp()
    return x_exp / x_exp.sum(1, keepdim=True)


@triton.jit
def softmax_kernel(x_ptr, z_ptr, N0, N1, T, B0: tl.constexpr, B1: tl.constexpr):
    """2 loops ver."""
    block_id_i = tl.program_id(0)
    log2_e = 1.44269504
    # Finish me!
    
    off_i = block_id_i * B0 + tl.arange(0, B0)
    mask_i = off_i < N0
    
    max = tl.full([B0], -float("inf"), dtype=tl.float32)
    
    for id_j in tl.range(0, T, B1):
        off_j = id_j + tl.arange(0, B1)
        mask_j = off_j < T
        off_ij = off_i[:, None] * T + off_j[None, :]
        mask_ij = mask_i[:, None] & mask_j[None, :]
        x = tl.load(x_ptr + off_ij, mask = mask_ij)
        max = tl.maximum(max, tl.max(x, axis = 1))
    
    sum = tl.zeros([B0], dtype=tl.float32)
    
    for id_j in tl.range(0, T, B1):
        off_j = id_j + tl.arange(0, B1)
        mask_j = off_j < T
        off_ij = off_i[:, None] * T + off_j[None, :]
        mask_ij = mask_i[:, None] & mask_j[None, :]
        x = tl.load(x_ptr + off_ij, mask = mask_ij)
        exp_x = tl.exp2(log2_e * (x - max[:, None]))
        sum += tl.sum(exp_x, axis=1)
            
    for id_j in tl.range(0, T, B1):
        off_j = id_j + tl.arange(0, B1)
        mask_j = off_j < T
        off_ij = off_i[:, None] * T + off_j[None, :]
        mask_ij = mask_i[:, None] & mask_j[None, :]
        x = tl.load(x_ptr + off_ij, mask = mask_ij)
        exp_x = tl.exp2(log2_e * (x - max[:, None]))
        # print(type(exp_x), type(sum[:, None]))
        z = exp_x / sum[:, None]
        tl.store(z_ptr + off_ij, z, mask=mask_ij)   
    
    return


@triton.jit
def softmax_kernel_brute_force(
    x_ptr, z_ptr, N0, N1, T, B0: tl.constexpr, B1: tl.constexpr
):
    """3 loops ver."""
    block_id_i = tl.program_id(0)
    log2_e = 1.44269504
    # Finish me!
    return


r"""
## Puzzle 9: Simple FlashAttention

A scalar version of FlashAttention.

Uses zero programs. Block size `B0` represent the batches of `q` to process out of `N0`. Sequence length is `T`. Process it `B1 < T` elements (`k`, `v`) at a time for some `B1`.

.. math::
    z_{i} = \sum_{j=1}^{T} \text{softmax}(q_i k_1, \ldots, q_i k_T)_j v_{j} \text{ for } i = 1\ldots N_0

This can be done in 1 loop using a similar trick from the last puzzle.

Hint: Use `tl.where` to mask `q dot k` to -inf to avoid overflow (NaN).
"""


def flashatt_spec(
    q: Float32[200,], k: Float32[200,], v: Float32[200,]
) -> Float32[200,]:
    x = q[:, None] * k[None, :]
    x_max = x.max(1, keepdim=True)[0]
    x = x - x_max
    x_exp = x.exp()
    soft = x_exp / x_exp.sum(1, keepdim=True)
    return (v[None, :] * soft).sum(1)


@triton.jit
def flashatt_kernel(
    q_ptr, k_ptr, v_ptr, z_ptr, N0, T, B0: tl.constexpr, B1: tl.constexpr
):
    block_id_i = tl.program_id(0)
    log2_e = 1.44269504
    myexp = lambda x: tl.exp2(log2_e * x)
    # Finish me!
    
    off_i = block_id_i * B0 + tl.arange(0, B0)
    mask_i = off_i < N0
    
    
    qk_max = tl.full([B0], -1.0e6, dtype=tl.float32)
    old_max = tl.full([B0], -1.0e6, dtype=tl.float32)
    z = tl.zeros([B0], dtype = tl.float32)
    sum = tl.zeros([B0], dtype = tl.float32)
    q = tl.load(q_ptr + off_i, mask=mask_i)
    
    
    for id_j in tl.range(0, T, B1):
        off_j = id_j + tl.arange(0, B1)
        mask_j = off_j < T
        off_ij = off_i[:, None] * T + off_j[None, :]
        mask_ij = mask_i[:, None] & mask_j[None, :]
        # q = tl.load(q_ptr + off_ij, mask=mask_ij)
        k = tl.load(k_ptr + off_j, mask=mask_j)
        v = tl.load(v_ptr + off_j, mask=mask_j, other=0.0)
        qk = q[:, None] * k[None, :] + tl.where(mask_ij, 0, -1.0e6)
        qk_max = tl.maximum(old_max, tl.max(qk, axis = 1))
        qk_exp = myexp(qk - qk_max[:, None])
        factor = myexp(old_max - qk_max)
        sum = sum * factor
        sum += tl.sum(qk_exp, axis = 1)
        z = z * factor + tl.sum(qk_exp * v[None, :], axis = 1)
        
        old_max = qk_max
        
    z = z / sum
    tl.store(z_ptr + off_i, z, mask = mask_i)
    
    return


r"""
## Puzzle 10: Two Dimensional Convolution

A batched 2D convolution.

Uses one program id axis. Block size `B0` represent the batches to process out of `N0`.
Image `x` is size is `H` by `W` with only 1 channel, and kernel `k` is size `KH` by `KW`.

.. math::
    z_{i, j, l} = \sum_{oj, ol}^{j+oj\le H, l+ol\le W} k_{oj,ol} \times x_{i,j + oj, l + ol} 
    \text{ for } i = 1\ldots N_0 \text{ for } j = 1\ldots H \text{ for } l = 1\ldots W
"""


def conv2d_spec(x: Float32[4, 8, 8], k: Float32[4, 4]) -> Float32[4, 8, 8]:
    z = torch.zeros(4, 8, 8)
    x = torch.nn.functional.pad(x, (0, 4, 0, 4, 0, 0), value=0.0)
    # print(x.shape, k.shape)
    for i in range(8):
        for j in range(8):
            z[:, i, j] = (k[None, :, :] * x[:, i : i + 4, j : j + 4]).sum(1).sum(1)
    return z


@triton.jit
def conv2d_kernel(
    x_ptr, k_ptr, z_ptr, N0, H, W, KH: tl.constexpr, KW: tl.constexpr, B0: tl.constexpr
):
    block_id_i = tl.program_id(0)
    off_i = block_id_i * B0 + tl.arange(0, B0)
    mask_i = off_i < N0
    
    off_h = tl.arange(0, KH)
    off_w = tl.arange(0, KW)
    off_hw = off_h[:, None] * KW + off_w[None, :]
    kernel = tl.load(k_ptr + off_hw)
    
    for j in tl.range(0, H):
        for k in tl.range(0, W):
            off_j = off_h[None, :, None] + j
            off_k = off_w[None, None, :] + k 
            off_jk = off_i * H * W + off_j * W + off_k
            mask_jk = (off_j < H) & (off_k < W)
            x = tl.load(x_ptr + off_jk, mask=mask_jk)
            
            z = tl.sum(x * kernel[None, :])
            off_z = off_i * H * W + j * W + k
            tl.store(z_ptr + off_z, z)     
     
    # Finish me!
    return


r"""
## Puzzle 11: Matrix Multiplication

A blocked matrix multiplication.

Uses three program id axes. Block size `B2` represent the batches to process out of `N2`.
Block size `B0` represent the rows of `x` to process out of `N0`. Block size `B1` represent the cols 
of `y` to process out of `N1`. The middle shape is `MID`.

.. math::
    z_{i, j, k} = \sum_{l} x_{i,j, l} \times y_{i, l, k} \text{ for } i = 1\ldots N_2, j = 1\ldots N_0, k = 1\ldots N_1

You are allowed to use `tl.dot` which computes a smaller mat mul.

Hint: the main trick is that you can split a matmul into smaller parts.

.. math::
    z_{i, j, k} = \sum_{l=1}^{L/2} x_{i,j, l} \times y_{i, l, k} +  \sum_{l=L/2}^{L} x_{i,j, l} \times y_{i, l, k}
"""


def dot_spec(x: Float32[4, 32, 32], y: Float32[4, 32, 32]) -> Float32[4, 32, 32]:
    return x @ y

import torch

@triton.jit
def dot_kernel(
    x_ptr,
    y_ptr,
    z_ptr,
    N0,
    N1,
    N2,
    MID,
    B0: tl.constexpr,
    B1: tl.constexpr,
    B2: tl.constexpr,
    B_MID: tl.constexpr,
):
    block_id_n = tl.program_id(0)
    block_id_m = tl.program_id(1)
    block_id_i = tl.program_id(2)
    # Finish me!
    
    off_i = block_id_i * B2 + tl.arange(0, B2)
    mask_i = off_i < N2
    
    off_m = block_id_m * B1 + tl.arange(0, B1)
    off_n = block_id_n * B0 + tl.arange(0, B0)
    # off_jk = off_j[None,:,None] * N0 + off_i[None,None,:]
    mask_m = off_m < N1
    mask_n = off_n < N0
    # mask_jk = (off_j < B1) & (off_k < B0)
    
    off_z = (off_i[:,None,None] * N0 * N1 + 
             off_m[None,:,None] * N0 +
             off_n[None,None,:])
    
    z = tl.zeros((B2, B1, B0), dtype=tl.float32)
    mask_z = mask_i[:,None,None] & mask_m[None,:,None] & mask_n[None,None,:]
    
    z = tl.zeros((4,3,3), dtype=tl.float32)
    # z_0 = z[0, 0, 0]
    
    for k in tl.range(0, MID, B_MID):
        off_k = k + tl.arange(0, B_MID)
        mask_k = off_k < MID
        off_x = (off_i[:,None,None] * N1 * MID +
                off_m[None,:,None] * MID +
                off_k[None,None,:]
        )
        off_y = (off_i[:,None,None] * N0 * MID +
                off_k[None,:,None] * N0 +
                off_n[None,None,:]
        )
        mask_x = mask_i[:, None, None] & mask_m[None, :, None] & mask_k[None, None, :]
        mask_y = mask_i[:, None, None] & mask_k[None, :, None] & mask_n[None, None, :]       
        x = tl.load(x_ptr + off_x, mask=mask_x)
        y = tl.load(y_ptr + off_y, mask=mask_y)
        # x_slice = x[:, 0:1]
        z += tl.dot(x, y)
        
    tl.store(z_ptr + off_z, z, mask=mask_z)    
    return


r"""
## Puzzle 12: Quantized Matrix Mult

When doing matrix multiplication with quantized neural networks a common strategy is to store the weight matrix in lower precision, with a shift and scale term.

For this problem our `weight` will be stored in 4 bits. We can store `FPINT` of these in a 32 bit integer. In addition for every `group` weights in order we will store 1 `scale` float value and 1 `shift` 4 bit value. We store these for the column of weight. The `activation`s are stored separately in standard floats.

Mathematically it looks like.

.. math::
    z_{j, k} = \sum_{l} sc_{j, \frac{l}{g}} (w_{j, l} - sh_{j, \frac{l}{g}}) \times y_{l, k} 
    \text{ for } j = 1\ldots N_0, k = 1\ldots N_1

Where `g` is the number of groups (`GROUP`).

However, it is a bit more complex since we need to also extract the 4-bit values into floats to begin.

Note:
- We don't consider batch size, i.e. `i`, in this puzzle.
- Remember to unpack the `FPINT` values into separate 4-bit values. This contains some shape manipulation.
"""

FPINT = 32 // 4
GROUP = 8


def quant_dot_spec(
    scale: Float32[32, 8],
    offset: Int32[32,],
    weight: Int32[32, 8],
    activation: Float32[64, 32],
) -> Float32[32, 32]:
    offset = offset.view(32, 1)

    def extract(x):
        over = torch.arange(8) * 4
        mask = 2**4 - 1
        return (x[..., None] >> over) & mask

    scale = scale[..., None].expand(-1, 8, GROUP).contiguous().view(-1, 64)
    offset = (
        extract(offset)[..., None].expand(-1, 1, 8, GROUP).contiguous().view(-1, 64)
    )
    return (scale * (extract(weight).view(-1, 64) - offset)) @ activation


@triton.jit
def quant_dot_kernel(
    scale_ptr,
    offset_ptr,
    weight_ptr,
    activation_ptr,
    z_ptr,
    N0,
    N1,
    MID,
    B0: tl.constexpr,
    B1: tl.constexpr,
    B_MID: tl.constexpr,
):
    block_id_row = tl.program_id(0)
    block_id_col = tl.program_id(1)
    
    Row = N0
    Col = N1
    off_row = block_id_row * B0 + tl.arange(0, B0)
    off_col = block_id_col * B1 + tl.arange(0, B1)
    mask_row = off_row < Row
    mask_col = off_col < Col
    z = tl.zeros((B0, B1), dtype=tl.float32)
    # (B0,)->(B0,1)
    off_z = off_row[:, None] * N1 + off_col[None, :]
    mask_z = mask_row[:, None] & mask_col[None, :]
    
    # (M, K) -> (M, K/4)
    for k in tl.range(0, MID, B_MID):
        off_k = k + tl.arange(0, B_MID)
        mask_k = off_k < MID
        
        # load activate
        off_ac = off_k[:, None] * N1 + off_col[None, :]
        mask_ac = mask_k[:, None] & mask_col[None, :]
        activate = tl.load(activation_ptr + off_ac, mask=mask_ac)
        # print(B0)
        # print(activate.shape)
        
        # load scale
        off_k_group = (k // GROUP) + tl.arange(0, B_MID // GROUP)
        mask_k_group = off_k_group < (MID // GROUP)
        off_scale_group = off_row[:, None] * (MID // GROUP) + off_k_group[None, :]
        mask_scale_group = mask_row[:, None] & mask_k_group[None, :]
        scale_group = tl.load(scale_ptr + off_scale_group, mask=mask_scale_group)
        # print(off_scale_group)
        
        # load shift
        off_k_group_Pack = (k // GROUP // FPINT) + tl.arange(0, B_MID // GROUP // FPINT)
        mask_k_group_Pack = off_k_group_Pack < (MID // GROUP // FPINT)
        off_shift_group_pack = off_row[:, None] * (MID // GROUP // FPINT) + off_k_group_Pack[None, :]
        mask_shift_group_pack = mask_row[:, None] & mask_k_group_Pack[None, :]
        #print(off_row[:, None])
        #print(mask_k_group_Pack[None, :])
        #print(mask_shift_group_pack)
        shift_group_Pack = tl.load(offset_ptr + off_shift_group_pack, mask=mask_shift_group_pack)
        # (16, 1)
        # print(shift_group_Pack)
        # print(B0)
        # print(off_shift_group_pack, off_row)
        # test = tl.load(offset_ptr + off_row, mask=mask_row)
        # print(shift_group_Pack, test)
        
        
        # load weight
        # (0, 16)
        off_k_INT4_Pack = (k // FPINT) + tl.arange(0, B_MID // FPINT)
        mask_k_INT4_Pack = off_k_INT4_Pack < (MID // FPINT)
        off_weight_Pack = off_row[:, None] * (MID // FPINT) + off_k_INT4_Pack[None, :]
        mask_weight_Pack = mask_row[:, None] & mask_k_INT4_Pack[None, :]
        weight_Pack = tl.load(weight_ptr + off_weight_Pack, mask=mask_weight_Pack)
        # print(off_weight_Pack)
        # print(weight_Pack.shape)
        # Unpack weight and shift
        # print("here", shift_group_Pack.shape)
        
        BITS = 4
        off_unpack = tl.arange(0, FPINT) * BITS
        unpack_mask = (1 << BITS) - 1
        shift = (shift_group_Pack >> off_unpack) & unpack_mask
        weight = (weight_Pack[:,:,None] >> off_unpack) & unpack_mask
        # print(shift.shape, weight.shape)
        
        # print(scale_group.shape, weight.shape, shift.shape)
        new_weight = scale_group[:,:,None] * (
            weight - shift[:,:,None]
        )
        # print(new_weight)
        
        new_weight = new_weight.reshape(
           B0, 64
        )
        # print(new_weight.shape)
        
        z += tl.dot(new_weight, activate)
    
    tl.store(z_ptr + off_z, z, mask=mask_z)
    return


def run_demos():
    run_demo1()
    run_demo2()
    run_demo3()
    run_demo4()


def run_puzzles(args, puzzles: List[int]):
    print_log = args.log
    device = args.device

    if 1 in puzzles:
        print("Puzzle #1:")
        ok = test(
            add_kernel,
            add_spec,
            nelem={"N0": 32},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 2 in puzzles:
        print("Puzzle #2:")
        ok = test(
            add_mask2_kernel,
            add2_spec,
            nelem={"N0": 200},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 3 in puzzles:
        print("Puzzle #3:")
        ok = test(
            add_vec_kernel,
            add_vec_spec,
            nelem={"N0": 32, "N1": 32},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 4 in puzzles:
        print("Puzzle #4:")
        ok = test(
            add_vec_block_kernel,
            add_vec_block_spec,
            nelem={"N0": 100, "N1": 90},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 5 in puzzles:
        print("Puzzle #5:")
        ok = test(
            mul_relu_block_kernel,
            mul_relu_block_spec,
            nelem={"N0": 100, "N1": 90},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 6 in puzzles:
        print("Puzzle #6:")
        ok = test(
            mul_relu_block_back_kernel,
            mul_relu_block_back_spec,
            nelem={"N0": 100, "N1": 90},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 7 in puzzles:
        print("Puzzle #7:")
        ok = test(
            sum_kernel,
            sum_spec,
            B={"B0": 1, "B1": 32},
            nelem={"N0": 4, "N1": 32, "T": 200},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 8 in puzzles:
        print("Puzzle #8:")
        ok = test(
            softmax_kernel,
            softmax_spec,
            B={"B0": 1, "B1": 32},
            nelem={"N0": 4, "N1": 32, "T": 200},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 9 in puzzles:
        print("Puzzle #9:")
        ok = test(
            flashatt_kernel,
            flashatt_spec,
            B={"B0": 64, "B1": 32},
            nelem={"N0": 200, "T": 200},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 10 in puzzles:
        print("Puzzle #10:")
        ok = test(
            conv2d_kernel,
            conv2d_spec,
            B={"B0": 1},
            nelem={"N0": 4, "H": 8, "W": 8, "KH": 4, "KW": 4},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 11 in puzzles:
        print("Puzzle #11:")
        ok = test(
            dot_kernel,
            dot_spec,
            B={"B0": 16, "B1": 16, "B2": 1, "B_MID": 16},
            nelem={"N0": 32, "N1": 32, "N2": 4, "MID": 32},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    if 12 in puzzles:
        print("Puzzle #12:")
        ok = test(
            quant_dot_kernel,
            quant_dot_spec,
            B={"B0": 16, "B1": 16, "B_MID": 64},
            nelem={"N0": 32, "N1": 32, "MID": 64},
            print_log=print_log,
            device=device,
        )
        print_end_line()
        if not ok:
            return
    print("All tests passed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--puzzle", type=int, metavar="N", help="Run Puzzle #N")
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run all Puzzles. Stop at first failure.",
    )
    parser.add_argument("-l", "--log", action="store_true", help="Print log messages.")
    parser.add_argument(
        "-i",
        "--intro",
        action="store_true",
        help="Run all demos in the introduction part.",
    )

    args = parser.parse_args()

    if os.getenv("TRITON_INTERPRET", "0") == "1":
        torch.set_default_device("cpu")
        args.device = "cpu"
    else:  # GPU mode
        torch.set_default_device("cuda")
        args.device = "cuda"

    if args.intro:
        run_demos()
    elif args.all:
        run_puzzles(args, list(range(1, 13)))
    elif args.puzzle:
        run_puzzles(args, [int(args.puzzle)])
    else:
        parser.print_help()
