# `flepimop2-ipynbrender`

An external provider package for [flepimop2](https://github.com/ACCIDDA/flepimop2) that provides a `IpynbRenderProcess` class for rendering jupyter notebooks as a processing step.

This package contributes the `ipynbrender` process module to the `flepimop2.process` namespace. Once installed, flepimop2 configurations can reference it via:

```yaml
process:
  report:
    module: ipynbrender
    file: ./analysis/report.ipynb
    output: ./model_output/report.html
```

## Installation

Like other packages in the `flepimop2-extras` package it can either be installed directly via:

```bash
pip install "flepimop2-ipynbrender@git+https://github.com/ACCIDDA/flepimop2-extras.git@main#subdirectory=packages/flepimop2-ipynbrender"
```

or as a part of a dependency group in `flepimop2-extras` if you're using multiple modules from this package:

```bash
pip install "flepimop2-extras[ipynbrender]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"
# or
pip install "flepimop2-extras[all]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"
```

## Configuration

| Item | Example | Role |
| --- | --- | --- |
| Configuration section | `process.report` | A named processing step |
| Input | `analysis/report.ipynb` | An existing notebook, including its stored outputs |
| Output | `model_output/report.html` | Rendered report; format is inferred from its extension |
| Optional format | `format: html` | Explicit nbconvert output format |
| Optional version | `version: 4` | Notebook format used while reading and validating |

The provider invokes `jupyter nbconvert` to render stored notebook outputs.
It does not add `--execute`, so run the analysis that produces figures and
tables before rendering. PDF and browser-based formats require nbconvert's
corresponding external tools; HTML is a convenient first example.

The `ipynbrender` module can be configured in your YAML configuration file with the following settings:

```yaml
process:
  my_notebook:
    module: ipynbrender
    file: ./model_input/notebooks/my_notebook.ipynb
    output: ./model_output/notebooks/my_notebook.pdf
    ...
```

- `file`: Corresponds to the source notebook to render.
- `output`: Corresponds to the output file to render the notebook to.
- `format`: The format to render the output to. Must be one of 'html', 'latex', 'pdf', 'webpdf', 'slides', 'markdown', 'asciidoc', 'rst', or 'notebook'. If not explicitly provided it will be inferred based on the file extension of the `output`.
- `version`: The version of the notebook format to return. If not specified the notebook version will not be converted from the format that it is currently in.
