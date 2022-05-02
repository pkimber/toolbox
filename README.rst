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

Parse the ``pillar`` and find the configuration for each site / domain.

.. tip:: Create a Digital Ocean *Personal access token* and add to your
         ``.private`` file.

::

  python3 -m venv venv-toolbox
  source .env.fish

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
