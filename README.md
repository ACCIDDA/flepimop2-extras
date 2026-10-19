# `flepimop2-extras`

`flepimop2-extras` contains optional provider packages for `flepimop2`.
They are maintained separately from the core because they serve specialized
workflows or require additional dependencies.

## Installation

These alpha packages currently use the shared development version `0.3.0dev`.
They are available from source; the metapackage and its providers have not been
published on PyPI. Use a virtual environment and one of the source options below.


### Installing Directly

For example, install the notebook-rendering provider directly:

```bash
pip install "flepimop2-ipynbrender@git+https://github.com/ACCIDDA/flepimop2-extras.git@main#subdirectory=packages/flepimop2-ipynbrender"
```

To install other packages directly you can replace `flepimop2-ipynbrender` in the command above with your preferred package.

### Installing From the `flepimop2-extras` Meta Package

The `flepimop2-extras` metapackage declares optional provider dependencies by
package name. Installing the metapackage from Git alone does not tell pip where
to obtain those unpublished dependencies. Clone the repository and supply the
local provider packages in the same installation command:

```bash
git clone https://github.com/ACCIDDA/flepimop2-extras.git
cd flepimop2-extras

# One provider through the metapackage:
python -m pip install ./packages/flepimop2-ipynbrender '.[ipynbrender]'

# All currently included providers through the metapackage:
python -m pip install ./packages/flepimop2-ipynbrender ./packages/flepimop2-slurm '.[all]'
```

For a reproducible installation, check out the desired commit before installing.
Developers can instead use the repository's
[`uv` workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with
`uv sync --all-packages`; see [Contributing](CONTRIBUTING.md).

## Package Index

Below is an index of the current packages included in `flepimop2-extras`.

- Module Name: Corresponds to the name of the module provided. I.e. the string you'd use to reference the module in configuration.
- Module Type: Corresponds to the type of module provided. I.e. the configuration section where you'd reference the module.
- Package: The name of the package if you wanted to install it directly.
- `flepimop2-extras` Extras: The extra groups that the module is included in.
- Documentation: Link to the documentation for the module.

| Module Name   | Module Type | Package                 | `flepimop2-extras` Extras | Documentation                                    |
| ------------- | ----------- | ----------------------- | ------------------------- | ------------------------------------------------ |
| `ipynbrender` | `process`   | `flepimop2-ipynbrender` | `all`, `ipynbrender`      | [Link](packages/flepimop2-ipynbrender/README.md) |
| `slurm`       | `job`       | `flepimop2-slurm`       | `all`, `slurm`            | [Link](packages/flepimop2-slurm/README.md)       |

## Contributing

Contributions are welcomed and appreciated! Please see the [contributing guide](CONTRIBUTING.md) for details on development setup, code standards, testing, and the pull request process.

## Funding Acknowledgement

This project was made possible by the Insight Net cooperative agreement CDC-RFA-FT-23-0069 from the CDC’s Center for Forecasting and Outbreak Analytics. Its contents are solely the responsibility of the authors and do not necessarily represent the official views of the Centers for Disease Control and Prevention.
