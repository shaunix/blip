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
  img = document.getElementById ('img-' + id);
  if (img.className == 'expander-img') {
    if (open) {
      img.src = img.src.replace('closed', 'open');
    } else {
      img.src = img.src.replace('open', 'closed');
    }
  }
}

function ellip (id) {
  var lnk = document.getElementById ('elliplnk-' + id);
  lnk.parentNode.removeChild (lnk);
  var txt = document.getElementById ('elliptxt-' + id);
  txt.className = '';
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

function replace_content (id, url) {
  var httpreq = false;
  if (window.XMLHttpRequest) {
    httpreq = new XMLHttpRequest();
  }
  else if (window.ActiveXObject) {
    try {
      httpreq = new ActiveXObject("Msxml2.XMLHTTP");
    } catch (e) {
      try {
        httpreq = new ActiveXObject("Microsoft.XMLHTTP");
      } catch (e) {}
    }
  }

  var el = document.getElementById (id);
  for (var par = el.parentNode; par; par = par.parentNode) {
    if (par.className == 'info') {
      break
    }
  }
  var mask = null;
  if (par) {
    mask = document.createElement('div');
    /* FIXME: i18n */
    mask.appendChild(document.createTextNode('Please wait'));
    mask.className = 'infomask';
    mask.style.width = par.clientWidth + 'px';
    mask.style.height = par.clientHeight + 'px';
    par.parentNode.insertBefore(mask, par);
  }

  /* we should show some sort of activity thingy */
  httpreq.onreadystatechange = function() {
    if (httpreq.readyState == 4) {
      par.parentNode.removeChild(mask);
      if (httpreq.status == 200) {
        el.innerHTML = httpreq.responseText;
      }
    }
  }
  httpreq.open('GET', url, true);
  httpreq.send(null);
}
