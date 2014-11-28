from setuptools import setup

setup(
    name='toolbox',
    version='0.1',
    py_modules=['toolbox'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        toolbox=toolbox:cli
    ''',
)
