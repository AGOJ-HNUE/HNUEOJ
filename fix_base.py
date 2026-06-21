with open("/home/agoj/site/templates/base.html", "r", encoding="utf-8") as f:
    content = f.read()

# Remove the script block I added in <head> which is useless
content = content.replace(
    """    <script>
      if (localStorage.getItem('sidebar-collapsed') === 'true') {
        document.documentElement.style.setProperty('--sidebar-initial-state', 'collapsed');
      }
    </script>""",
    "",
)

# Ensure we don't duplicate inline scripts
nav_script = "\n    <script>if (localStorage.getItem('sidebar-collapsed') === 'true') { document.getElementById('navigation').classList.add('collapsed'); }</script>\n"
if nav_script not in content:
    nav_end = content.find("</nav>") + 6
    content = content[:nav_end] + nav_script + content[nav_end:]

page_script = "\n      <script>if (localStorage.getItem('sidebar-collapsed') === 'true') { document.getElementById('page-container').classList.add('collapsed'); }</script>\n"
if page_script not in content:
    page_container = content.find('<div id="page-container">') + 25
    content = content[:page_container] + page_script + content[page_container:]

with open("/home/agoj/site/templates/base.html", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed base.html")
