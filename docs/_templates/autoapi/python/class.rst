{% if obj.display %}
   {% if is_own_page %}
{{ obj.id }}
{{ "=" * obj.id | length }}

   {% endif %}
   {% set visible_children = obj.children|selectattr("display")|list %}
   {% set own_page_children = visible_children|selectattr("type", "in", own_page_types)|list %}
   {% if is_own_page and own_page_children %}
.. toctree::
   :hidden:

      {% for child in own_page_children %}
   {{ child.include_path }}
      {% endfor %}

   {% endif %}
.. py:{{ obj.type }}:: {% if is_own_page %}{{ obj.id }}{% else %}{{ obj.short_name }}{% endif %}{% if obj.type_params %}[{{ obj.type_params }}]{% endif %}{% if obj.args %}({{ obj.args }}){% endif %}

   {% for (args, return_annotation) in obj.overloads %}
      {{ " " * (obj.type | length) }}   {{ obj.short_name }}{% if args %}({{ args }}){% endif %}

   {% endfor %}
   {% if obj.bases %}
      {% if "show-inheritance" in autoapi_options %}

   Bases: {% for base in obj.bases %}{{ base|link_bases }}{% if not loop.last %}, {% endif %}{% endfor %}
      {% endif %}

      {% if "show-inheritance-diagram" in autoapi_options and obj.bases != ["object"] %}
   .. autoapi-inheritance-diagram:: {{ obj.obj["full_name"] }}
      :parts: 1
         {% if "private-members" in autoapi_options %}
      :private-bases:
         {% endif %}

      {% endif %}
   {% endif %}
   {% if obj.docstring %}

   {{ obj.docstring|indent(3) }}
   {% endif %}
   {% for obj_item in visible_children %}
      {% if obj_item.type not in own_page_types %}

   {{ obj_item.render()|indent(3) }}
      {% endif %}
   {% endfor %}
   {% if is_own_page and own_page_children %}
      {% for kind, title in [("attribute", "Attributes"), ("exception", "Exceptions"), ("class", "Classes"), ("method", "Methods")] %}
         {% set children = own_page_children|selectattr("type", "equalto", kind)|list %}
         {% if children %}
{{ title }}
{{ "-" * title|length }}

.. autoapisummary::

            {% for child in children %}
   {{ child.id }}
            {% endfor %}

         {% endif %}
      {% endfor %}
   {% endif %}
{% endif %}
