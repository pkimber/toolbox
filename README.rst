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

To calculate hosting costs:

Create a Digital Ocean *Personal access token* and Linode token and add to
your ``.private`` file e.g::

  set -x DIGITAL_OCEAN_TOKEN "dop_v1_12345..."
  set -x LINODE_TOKEN "cb12345..."

::

  python3 -m venv venv-toolbox
  pip install -r requirements.txt

  source .env.fish
  python domain-config.py

Copy ``domains.json`` and ``droplets.json`` to the current folder of your
``kbsoftware_couk`` project.

Run the management command to calculate hosting costs::

  django-admin 5774-domain-config

Open ``domain-config.csv`` in LibreOffice spreadsheets...

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
