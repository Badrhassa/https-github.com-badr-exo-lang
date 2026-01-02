from setuptools import setup

setup(
    name='exo-lang',
    version='3.1.0',
    description='لغة برمجية عربية/إنجليزية',
    author='BADR',
    py_modules=['exo'],
    entry_points={
        'console_scripts': [
            'exo=exo:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
)
