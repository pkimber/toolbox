Toolbox
*******

Three apps
==========

1. Check branches etc
---------------------

``kb.py``::

  cd ~/dev/app/my-app/
  pip install -r requirements.txt

  ln -s ~/dev/module/toolbox/kb.py .
  python kb.py

2. Domain Config
----------------

Read the ``pillar`` and find the configuration for each domain name::

  python3 -m venv venv-toolbox
  source venv-toolbox/bin/activate.fish

  python domain-config.py

3. Toolbox
----------

I am not sure what this does. It is installed using Click and ``setup.py``

::

  python3 -m venv venv-toolbox
  source venv-toolbox/bin/activate.fish
  pip install --editable .

  toolbox

Old Notes
=========

Not sure if the following commands will break the environment create above::

  pip install -r requirements.txt
  ln -s ../fabric/lib lib
