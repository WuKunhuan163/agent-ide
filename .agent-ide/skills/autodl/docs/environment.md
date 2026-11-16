# Environment: match the driver, then build upward

A rented box arrives with CUDA, torch and conda already installed. The job is not
to install a stack but to find out what is already there and add only what is
missing — every `pip install torch` on a working image is a chance to break the
driver match that the image was built to guarantee.

## Read the three facts first

**Three facts decide everything after them, and the block below prints all three at once** — architecture, image, disk layout.

```bash
autodl exec "$UUID" "python -V && nvcc -V | tail -2 && python -c 'import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available())' && nvidia-smi --query-gpu=name,driver_version --format=csv,noheader"
```

They answer, in order: which ABI a wheel must match, which CUDA toolkit can compile
an extension, whether torch can see the card, and which driver limits the runtime.

## The one hard constraint

A CUDA extension is compiled against a toolkit and a set of GPU architectures, and
loaded by a torch built for one CUDA runtime. Three numbers must agree:

```text
driver  >=  torch.version.cuda  ==  toolkit used to compile the extension (nvcc -V)
```

and the compiled `-gencode arch=...` list must include the card's compute capability:

```bash
autodl exec "$UUID" "python -c 'import torch;print(torch.cuda.get_device_capability())'"
```

A mismatch does not fail at install; it fails at the first kernel launch with
`no kernel image is available for execution on the device`, which reads like a
code bug.

When the mismatch is a choice, change **torch**, not the driver: the driver is fixed
by the host and cannot be upgraded from inside the container.

## Install order

1. **Do not touch torch.** If the image ships 2.x+cu121, that is the stack.
2. **Pure-Python dependencies** are safe: `diffusers`, `transformers`, `accelerate`,
   `trimesh`, `pyyaml`. Pin them to the versions the successful run used — a floating
   `diffusers>=0.35` silently changes behaviour between two runs of the same code.
3. **CUDA extensions last**, and only after 1 and 2 are proven by a one-step forward.

Cache and temp directories belong on the data disk, set before installing:

```bash
export PIP_CACHE_DIR=/root/autodl-tmp/cache/pip
export TMPDIR=/root/autodl-tmp/cache/tmp
```

## Proving an extension works

`import` is not proof: a compiled extension imports fine and raises on the first
kernel launch. The cheapest honest test is one forward pass on the real shape.

```bash
autodl exec "$UUID" "cd /root/autodl-tmp/project && python - <<'PY'
import torch
from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer
print('import ok')
# build the smallest settings this code path uses and run one rasterize call
PY"
```

If the code has a `--steps 1` or smoke flag, use that instead: it exercises the whole
path and answers the question you actually have.

## Wheel ABI

A wheel filename encodes its Python tag and platform, e.g. `cp312` / `linux_x86_64`.
`pip install x.whl` on python 3.13 with a `cp312` wheel says "not a supported wheel",
which sounds like a version problem and is an ABI problem. Check before installing:

```bash
autodl exec "$UUID" "python -c 'import sys,sysconfig;print(sys.version_info[:2], sysconfig.get_platform())'"
```

The fix is to rebuild for the interpreter in use, not to force-install the wrong one.
