function lcont_toggle (id) {
  var el = document.getElementById (id);
  open = true;
  for (var div = el.firstChild; div; div = div.nextSibling) {
    if (div.className == 'lcont-content') {
      div.className = 'lcont-hidden';
      open = false;
    }
    else if (div.className == 'lcont-hidden') {
      div.className = 'lcont-content';
    }
  }
  img = document.getElementById ('img-' + id);
  if (img.className == 'lcont-img') {
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
    mask.className = 'infomask';
    mask.style.width = par.clientWidth + 'px';
    mask.style.height = par.clientHeight + 'px';
    par.parentNode.insertBefore(mask, par);
    /* FIXME: i18n */
    el.innerHTML = 'Loading...';
  }

  /* we should show some sort of activity thingy */
  httpreq.onreadystatechange = function() {
    if (httpreq.readyState == 4) {
      if (httpreq.status == 200) {
        el.innerHTML = httpreq.responseText;
      } else {
        /* FIXME: i18n */
        el.innerHTML = 'Could not load content';
      }
      par.parentNode.removeChild(mask);
    }
  }
  httpreq.open('GET', url, true);
  httpreq.send(null);
}

function KeyedThing (key, thing) {
  this.key = key;
  this.thing = thing;
}
function KeyedThingNumSort (thing1, thing2) {
  if (thing1 == false) {
    return true;
  }
  else if (thing2 == false) {
    return false;
  }
  else {
    return thing1.key - thing2.key
  }
}
function KeyedThingLexSort (thing1, thing2) {
  if (thing1 == false) {
    return -1;
  }
  else if (thing2 == false) {
    return 1;
  }
  else if (thing1.key == thing2.key) {
    return 0;
  }
  else if (thing1.key < thing2.key) {
    return -1;
  }
  else {
    return 1;
  }
}
function sort (cls, key) {
  var things = []
  var els = document.getElementsByTagName ('table');
  for (var i = 0; i < els.length; i++) {
    if (has_class (els[i], cls)) {
      var spans = els[i].getElementsByTagName ('span');
      var el_key = false;
      for (var k = 0; k < spans.length; k++) {
        if (has_class (spans[k], key)) {
          el_key = spans[k].innerHTML;
          break;
        }
      }
      keyed = new KeyedThing (el_key, els[i]);
      things.push (keyed);
    }
  }
  dummies = []
  for (var i = 0; i < things.length; i++) {
    dummy = document.createElement ('div');
    dummies.push (dummy);
    things[i].thing.parentNode.replaceChild (dummy, things[i].thing);
  }
  things.sort (KeyedThingLexSort);
  for (var i = 0; i < things.length; i++) {
    dummies[i].parentNode.replaceChild (things[i].thing, dummies[i]);
  }
}
function has_class (el, cls) {
  var el_cls = el.className.split(' ');
  for (var i = 0; i < el_cls.length; i++) {
    if (cls == el_cls[i]) {
      return true;
    }
  }
  return false;
}
