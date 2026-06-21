with open("templates/base.html", "r", encoding="utf-8") as f:
    content = f.read()

nav_end = content.find("</nav>") + 6
content = (
    content[:nav_end]
    + "\n    <script>if (localStorage.getItem('sidebar-collapsed') === 'true') { document.getElementById('navigation').classList.add('collapsed'); }</script>\n"
    + content[nav_end:]
)

page_container = content.find('<div id=" page-container\>')
