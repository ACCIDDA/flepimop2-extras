# `flepimop2-extras`

A collection of common modules that are used frequently in practice in conjunction with `flepimop2`. 

These modules have been separated from core `flepimop2` because they're specialized or require major dependencies. It also makes it much easier for developers to contribute/work on individual modules without having to think about affecting core `flepimop2` pipeline elements.

## Installation

Packages in this repository can be installed by a user one of two ways:

1) Installing the module package directly, or
2) Installing modules via the `flepimop2-extras` meta package.

### Installing Directly

For example, suppose you want to install the `flepimop2-ipynbrender` package with provides the `ipynbrender` process module:

```bash
pip install "flepimop2-ipynbrender@git+https://github.com/ACCIDDA/flepimop2-extras.git@main#subdirectory=packages/flepimop2-ipynbrender"
```

To install other packages directly you can replace `flepimop2-ipynbrender` in the command above with your preferred package.

### Installing From the `flepimop2-extras` Meta Package

To make working on the codebase easier for the developers of this package the individual packages are managed via a [`uv` workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/). This means that the dependencies across all constituent packages are consistently managed together and the `flepimop2-extras` package is a thin meta package. You can install the desired modules by installing `flepimop2-extras` package with the appropriate extra:

```bash
# If you want to install the `flepimop2-ipynbrender` module:
pip install "flepimop2-extras[ipynbrender]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"

# If you want to install multiple modules, such as `flepimop2-ipynbrender` and `flepimop2-slurm`:
pip install "flepimop2-extras[ipynbrender,slurm]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"

# If you want to install all modules in the `flepimop2-extras` package:
pip install "flepimop2-extras[all]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"
```

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
