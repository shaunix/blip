function expander_toggle (id) {
  var el = document.getElementById (id);
  open = true;
  for (var div = el.firstChild; div; div = div.nextSibling) {
    if (div.className == 'expander-content') {
      div.className = 'expander-hidden';
      open = false;
    }
    else if (div.className == 'expander-hidden') {
      div.className = 'expander-content';
    }
  }
  img = el.getElementsByTagName ('img');
  for (var i = 0; i < img.length; i++) {
    if (img[i].className == 'expander-img') {
      if (open) {
        img[i].src = img[i].src.replace('closed', 'open');
      } else {
        img[i].src = img[i].src.replace('open', 'closed');
      }
    }
  }
}

function tab (id) {
  var el = document.getElementById (id);
  var par = el.parentNode;
  for (var div = par.firstChild; div; div = div.nextSibling) {
    if (div.className == 'tabbed-tabs') {
      var tabs = div.getElementsByTagName('td');
      for (var i=0; i < tabs.length; i++) {
        var tab = tabs[i];
        if (tab.className == 'tabbed-tab-expanded') {
          if (tab.id != (id + '--tab')) {
            tab.className = 'tabbed-tab-collapsed';
          }
        }
        else if (tab.className == 'tabbed-tab-collapsed') {
          if (tab.id == (id + '--tab')) {
            tab.className = 'tabbed-tab-expanded';
          }
        }
      }
    }
    else if (div.className == 'tabbed-expanded') {
      if (div.id != id) {
        div.className = 'tabbed-collapsed';
      }
    }
    else if (div.className == 'tabbed-collapsed') {
      if (div.id == id) {
        div.className = 'tabbed-expanded';
      }
    }
  }
}
