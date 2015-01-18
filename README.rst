Toolbox
*******

Virtual Environment
-------------------

::

  pyvenv-3.4 --without-pip venv-toolbox
  source venv-toolbox/bin/activate
  wget https://raw.githubusercontent.com/pypa/pip/master/contrib/get-pip.py
  python get-pip.py
  pip install --editable .

Not sure if the following commands will break the environment create above::

  pip install -r requirements.txt
  ln -s ../fabric/lib lib

Usage
=====

::

  toolbox
