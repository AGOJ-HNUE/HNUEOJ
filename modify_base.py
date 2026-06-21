filepath = "/home/agoj/site/templates/base.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace #navigation block
start_tag = '<nav id="navigation" class="unselectable">'
end_tag = "</nav>"
start_idx = content.find(start_tag)
end_idx = content.find(end_tag, start_idx) + len(end_tag)

if start_idx != -1 and end_idx != -1:
    new_nav = """    <nav id="navigation" class="unselectable">
      <div id="nav-container">
        <ul id="nav-list">
          <li class="home-nav-element"><a href="{{ url('home') }}">{% include "site-logo-fragment.html" %}</a></li>
          <div id="sidebar-toggle" onclick="toggleSidebar()">
            <i class="fa fa-angle-double-left" id="sidebar-toggle-icon"></i>
            <span class="nav-text">{{ _('Collapse') }}</span>
          </div>
          <li class="home-menu-item"><a href="{{ url('home') }}" class="nav-home">
            <span class="nav-icon-container"><i class="fa fa-home"></i></span>
            <span class="nav-text">{{ _('Home') }}</span>
          </a></li>
          {% for node in mptt_tree(nav_bar) recursive %}
            <li>
              {% if node.key == "more" %}
                <a href="#" onclick="return false;"
                   class="nav-icon-link nav-{{ node.key }}{% if node.key in nav_tab %} active{% endif %}"
                   data-tooltip="{{ user_trans(node.label) }}">
                  <span class="nav-icon-container">
                    <i class="fa fa-ellipsis"></i>
                  </span>
                  <span class="nav-text">{{ user_trans(node.label) }}</span>
                  <i class="fa fa-angle-down" style="margin-left: auto;"></i>
                </a>
                {% with children=node.get_children() %}
                  {% if children %}
                    <div class="nav-dropdown">
                      {% for child in children %}
                        <a href="{{ child.path }}" class="nav-dropdown-item">
                          {{ user_trans(child.label) }}
                        </a>
                      {% endfor %}
                    </div>
                  {% endif %}
                {% endwith %}
              {% else %}
                <a href="{{ node.path }}"
                   class="nav-icon-link nav-{{ node.key }}{% if node.key in nav_tab %} active{% endif %}"
                   data-tooltip="{{ user_trans(node.label) }}">
                  <span class="nav-icon-container">
                    {% if node.key == "problems" %} <i class="fa fa-puzzle-piece"></i> {% endif %}
                    {% if node.key == "submit" %} <i class="fa fa-code"></i> {% endif %}
                    {% if node.key == "user" %} <i class="fa fa-user"></i> {% endif %}
                    {% if node.key == "contest" %} <i class="fa fa-ranking-star"></i> {% endif %}
                    {% if node.key == "group" %} <i class="fa fa-building-columns"></i> {% endif %}
                    {% if node.key == "courses" %} <i class="fa fa-graduation-cap"></i> {% endif %}
                    {% if node.key == "quiz" %} <i class="fa fa-file-alt"></i> {% endif %}
                  </span>
                  <span class="nav-text">{{ user_trans(node.label) }}</span>
                  {% with children=node.get_children() %}
                    {% if children %}
                      <i class="fa fa-angle-down" style="margin-left: auto;"></i>
                    {% endif %}
                  {% endwith %}
                </a>
                {% with children=node.get_children() %}
                  {% if children %}
                    <div class="nav-dropdown">
                      {% for child in children %}
                        <a href="{{ child.path }}" class="nav-dropdown-item">
                          {{ user_trans(child.label) }}
                        </a>
                      {% endfor %}
                    </div>
                  {% endif %}
                {% endwith %}
              {% endif %}
            </li>
          {% endfor %}
        </ul>

        <div class="nav-bottom-actions">
          {% if request.user.is_authenticated %}
            <span title="{{_('Chat')}}">
              <a id="chat-icon" href="{{ url('chat', '') }}" class="navbar-icon" aria-hidden="true">
                <i class="fab fa-weixin"></i>
                <span class="nav-text">{{ _('Chat') }}</span>
                {% set unread_chat = request.profile.get_num_unread_chat_boxes() %}
                {% if unread_chat %}
                  <sub class="unread_boxes">{{unread_chat}}</sub>
                {% endif %}
              </a>
            </span>

            {% set unseen_cnt = request.profile.get_num_unseen_notifications() %}
            <span title="{{_('Notification')}}" class="{{ 'notification-open' if unseen_cnt > 0 }}">
              <a href="{{ url('notification') }}" class="navbar-icon" id="notification" aria-hidden="true">
                <i class="far fa-bell"></i>
                <span class="nav-text">{{ _('Notification') }}</span>
                {% if unseen_cnt > 0 %}
                  <sub class="unread_boxes">{{unseen_cnt}}</sub>
                {% endif %}
              </a>
            </span>
          {% endif %}
          <span title="{{_('Language')}}">
            <div class="navbar-icon" id="nav-lang-icon" aria-hidden="true">
              <i class="fa fa-language"></i>
              {% if LANGUAGE_CODE == "vi" %}
                <h4 class="nav-right-text">Tiếng Việt</h4>
              {% endif %}
              {% if LANGUAGE_CODE == "en" %}
                <h4 class="nav-right-text">English</h4>
              {% endif %}
            </div>
            <div id="lang-dropdown" class="dropdown" role="tooltip">
              {% for language in language_info_list(LANGUAGES) %}
                <div value="{{ language.code }}" class="dropdown-item lang-dropdown-item"
                     style="{{'font-weight: bold' if language.code == LANGUAGE_CODE}}">
                  {{ language.name_local }}
                </div>
              {% endfor %}
              <div class="popper-arrow" data-popper-arrow></div>
            </div>
          </span>
          <span title="{{_('Dark Mode')}}">
            <a class="navbar-icon black" id="nav-darkmode-icon" aria-hidden="true" href="?darkmode=1">
                <i class="far fa-moon"></i>
                <span class="nav-text">{{ _('Dark Mode') }}</span>
            </a>
          </span>
          {% if request.user.is_authenticated %}
            <span>
                <div id="user-links">
                  <img class="user-img" src="{{ gravatar(request.profile.id, 32) }}" height="24" width="24" style="border-radius: 50%; margin-right: 15px;">
                  <span class="nav-right-text" style="font-weight: bold; flex-grow: 1;">{{ request.user.username }}</span>
                  <i class="fa fa-angle-down"></i>
                </div>
            </span>
            <div class="dropdown" id="userlink_dropdown" role="tooptip">
              <div class="popper-arrow" data-popper-arrow></div>
              <a href="{{ url('user_page') }}">
                <div class="dropdown-item"><i class="fa fa-user"></i> {{ _('Profile') }}</div>
              </a>
              {% if request.user.is_staff or request.user.is_superuser %}
                <a href="{{ url('admin:index') }}">
                  <div class="dropdown-item"><i class="fa fa-user-shield"></i> {{ _('Admin') }}</div>
                </a>
              {% endif %}
              {% if request.user.is_superuser %}
                <a href="{{ url('internal_problem_queue') }}">
                  <div class="dropdown-item"><i class="fa fa-circle-info"></i> {{ _('Internal') }}</div>
                </a>
                <a href="{{ url('site_stats') }}">
                  <div class="dropdown-item"><i class="fa fa-chart-pie"></i> {{ _('Stats') }}</div>
                </a>
              {% endif %}
              <a href="{{ url('user_bookmark') }}">
                <div class="dropdown-item"><i class="fa fa-bookmark"></i> {{ _('Bookmarks') }}</div>
              </a>
              {% if request.user|can_upload_files %}
                <a href="{{ url('custom_file_upload') }}">
                  <div class="dropdown-item"><i class="fa fa-upload"></i> {{ _('My Files') }}</div>
                </a>
              {% endif %}
              <a href="{{ url('user_edit_profile') }}">
                <div class="dropdown-item"><i class="fa fa-gear"></i> {{ _('Settings') }}</div>
              </a>
              <a href="{{ url('theme_settings') }}">
                <div class="dropdown-item"><i class="fa fa-palette"></i> {{ _('Theme') }}</div>
              </a>
              {% if request.user.is_impersonate %}
                <a href="{{ url('impersonate-stop') }}" data-force_new_page="1">
                  <div class="dropdown-item"><i class="fa fa-eye"></i> {{_('Stop impersonating')}}</div>
                </a>
              {% else %}
                <a href="#" id="logout" class="red">
                  <div class="dropdown-item"><i class="fa fa-right-from-bracket"></i>
                    {{ _('Log out') }}
                    <form id="logout-form" action="{{ url('auth_logout') }}" method="POST">
                      {% csrf_token %}
                    </form>
                  </div>
                </a>
              {% endif %}
            </div>
          {% else %}
            <span class="anon">
              <a href="{{ url('auth_login') }}?next={{ LOGIN_RETURN_PATH|urlencode }}">
                <i class="fa fa-sign-in-alt"></i>
                <h4 class="nav-right-text">{{ _('Log in') }}</h4>
              </a>
              <a href="{{ url('registration_register') }}">
                <i class="fa fa-user-plus"></i>
                <h4 class="nav-right-text">{{ _('Sign up') }}</h4>
              </a>
            </span>
          {% endif %}
        </div>
      </div>
    </nav>"""

    new_content = content[:start_idx] + new_nav + content[end_idx:]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Replaced navigation in base.html successfully.")
else:
    print("Could not find <nav> tags in base.html.")
