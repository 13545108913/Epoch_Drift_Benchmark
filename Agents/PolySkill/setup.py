#!/usr/bin/env python3
"""Setup script for PolySkill"""

from setuptools import setup, find_packages
import os

# Read README for long description
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "PolySkill: Learning Generalizable Skills Through Polymorphic Abstraction"

# Read requirements
requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
with open(requirements_path, "r", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="polyskill",
    version="0.1.0",
    description="Learning Generalizable Skills Through Polymorphic Abstraction for Web Agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Simon Yu, Gang Li, Weiyan Shi, Peng Qi",
    author_email="yu.chi@northeastern.edu",
    url="https://github.com/your-org/polyskill",  # Update with actual URL
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    entry_points={
        "console_scripts": [
            "polyskill-mind2web=polyskill.experiments.mind2web.run_mind2web:main",
            "polyskill-webarena=polyskill.experiments.webarena.run_webarena:main",
            "polyskill-explore=polyskill.experiments.self_proposing.run_self_proposing:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
