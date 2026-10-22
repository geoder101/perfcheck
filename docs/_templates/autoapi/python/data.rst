{% if obj.display %}
   {% if is_own_page %}
{{ obj.id }}
{{ "=" * obj.id | length }}

   {% endif %}
.. py:{% if obj.is_type_alias() %}type{% else %}{{ obj.type }}{% endif %}:: {% if is_own_page %}{{ obj.id }}{% else %}{{ obj.name }}{% endif %}
   {% if not obj.is_type_alias() %}
      {% if obj.annotation is not none %}

   :type: {% if obj.annotation %} {{ obj.annotation }}{% endif %}
      {% endif %}
      {% if obj.value is not none %}

         {% if obj.value.splitlines()|count > 1 %}
   :value: Multiline-String

   .. code-block:: python

      {{ obj.value|indent(width=6,blank=true) }}
         {% else %}
   :value: {{ obj.value|truncate(100) }}
         {% endif %}
      {% endif %}
   {% elif obj.value %}
{{ "\n" }}
   Alias expression (including validation metadata)::

      {{ obj.value|indent(width=6, first=false) }}
   {% endif %}
   {% if obj.docstring %}
{{ "\n" }}
   {{ obj.docstring|indent(3) }}
   {% endif %}
{% endif %}
