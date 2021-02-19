# Lazy Bloodhound

[Lazy Bloodhound](https://whnt.com/news/lazy-bloodhound-goes-out-for-morning-walk-finishes-7th-in-alabama-half-marathon/) is a toy static code analyzer built on [tree-sitter](https://tree-sitter.github.io/tree-sitter/). 

Tree-sitter is a parser-generator built and maintained by GitHub which generates really fast parsers. It has a number of supported grammars and language bindings.

Currently, Lazy Bloodhound contains a PHP analyzer checking for a single type of command injection. This project was created for a [HackOvert YouTube video](https://youtu.be/ZZxQhUMtyYc) about building a static code analyzer to find bugs quickly. It's main purpse is to constrast manual code auditing discussed in [this video](https://www.youtube.com/watch?v=96ui5ZsIeqQ).

The goal of Lazy Bloodhound is to merely demonstrate how we can build simple static analyzers to find bugs in source code.  Our current use case is finding command injection bugs in PHP, but you can write analyzers to find whatever you're interested in.

# Example alert

Sure thing. Consider the `smoketests/001.php` file. Let's analyze it and see what we get:
```
$ python3 lazy_bloodhound.py smoketests\001.php

Analyzing file: smoketests\001.php
[!] Alert: Possible command injection on line 12
    >>> exec("wr_mfg_data -m ".$_REQUEST['macAddress']." -c ".$_REQUEST['reginfo'],$dummy,$res)

Finished analyzing 1 file(s) in 0:00:00.002993. Found 1 alerts.
```
Woo that's fast! That smoketest is 120 lines of code parsed and analyzed in a fraction of a second. You can scan hundreds of PHP files in seconds. This command injection vulnerability comes from a [real software](https://www.cvedetails.com/cve/CVE-2016-1555/)! Cool, huh?


# Usage

```
python3 lazy_bloodhound.py -h
usage: lazy_bloodhound.py [-h] [-d] [-v] target

A really lazy (but super cute) PHP static code analyzer v0.1.0

positional arguments:
  target            file /path/to/target.php or directory /path/to/dir/

optional arguments:
  -h, --help        show this help message and exit
  -d, --debug-info  print parser warnings
  -v, --verbose     print all node data
```

In general, you'll simply want to aim `lazy_bloodhound.py` at a PHP file or directory containing PHP files and see what it digs up.

```
python3 lazy_bloodhound.py myfile.php
python3 lazy_bloodhound.py my/php/project/
```

You can get information about the abstract syntax tree (AST) as it's being walked by providing `-d/--debug-info` and/or `-v/--verbose` switches.

# Installing

This project requires the following:

* python3
* The `tree_sitter` python package from pip
* git

## Install process

Run these commands to get up and running.

```
pip3 install tree_sitter
git clone https://github.com/HackOvert/LazyBloodhound
cd LazyBloodhound
cd parsers
git clone https://github.com/tree-sitter/tree-sitter-php
cd ..
python3 build.py
```

Now you should be able to run the `lazy_bloodhound.py` file and analyze PHP like a boss.


# Building the library file

Above we run `python3 build.py` to genertae (build) the PHP parser. Let's peek inside that file:

```
from tree_sitter import Language, Parser

Language.build_library(
  'build/languages.so',

  # Include one or more languages
  [
    'parsers/tree-sitter-php',
  ]
)
```

This script imports the `Language` and `Parser` classes from `tree_sitter` and creates a shared object or DLL in the `build/` directory called `languages.so`. The `lazy_bloodhound.py` script will use this for parsing.

If we want to parse multi-language documents, we can simply add more tree-sitter grammars to the list in `build_library.py` and re-build to have access to more language parsers.

# Is this a virus?

No. Lazy Bloodhound is not a virus. As of mid Feb 2021 when you run a scan on a file with this single line of PHP:

```
<?php system('ls ' . $_GET['path']); ?>
```

Microsoft Windows Defender will alert with a "Backdoor:PHP/Dirtelti.MTG" signature. This is funny, but it's a false positive. I've decided to include this oddity in this README just in case you use Lazy Bloodhound and encounter a virus alert. Don't panic. 

The only dependency, `tree-sitter` is developed and maintained by GitHub. If that's somehow been backdoored, we have bigger problems to worry about.