function exp_toggle (id) {
  var el = document.getElementById (id);
  open = true;
  for (var div = el.firstChild; div; div = div.nextSibling) {
    if (div.className == 'exp-content') {
      div.className = 'exp-hidden';
      open = false;
    }
    else if (div.className == 'exp-hidden') {
      div.className = 'exp-content';
    }
  }
  img = document.getElementById ('img-' + id);
  if (img && img.className == 'exp-img') {
    if (open) {
      img.src = img.src.replace('closed', 'open');
    } else {
      img.src = img.src.replace('open', 'closed');
    }
  }
  slink = document.getElementById ('slink-' + id);
  if (slink && slink.className == 'slinks') {
    mask = document.getElementById ('slink-' + id + '-mask');
    if (!open) {
      if (!mask) {
        mask = document.createElement ('div');
        mask.id = 'slink-' + id + '-mask';
        mask.className = 'slinksmask';
        mask.style.width = slink.parentNode.clientWidth + 'px';
        mask.style.height = slink.parentNode.clientHeight + 'px';
        slink.parentNode.insertBefore(mask, slink);
      }
      mask.style.display = 'block';
    } else {
      mask.style.display = 'none';
    }
  }
}

function plink (id) {
  i = 1;
  el = document.getElementById ('plink' + i);
  while (el) {
    if (i != id) {
      el.style.display = 'none';
    }
    else if (el.style.display == 'block') {
      el.style.display = 'none';
      break;
    }
    else {
      el.style.display = 'block';
      bot = el.offsetTop + el.clientHeight;
      if (bot > window.innerHeight) {
        if (el.clientHeight > window.innerHeight) {
          newy = el.offsetTop;
        } else {
          newy = bot - window.innerHeight + 10
        }
        if (newy > window.pageYOffset) {
          window.scrollTo (0, newy);
        }
      }
    }
    i++;
    el = document.getElementById ('plink' + i);
  }
}

function get_offsetLeft (el) {
  if (el) {
    return el.offsetLeft + get_offsetLeft (el.offsetParent);
  } else {
    return 0;
  }
}

function showcomment (i, j, x) {
  gr = document.getElementById ('graph-' + i);
  el = document.getElementById ('comment-' + i + '-' + j);
  left = get_offsetLeft(gr) + x - 10;
  el.style.left = left + 'px';
  el.style.display = 'block';
}
function hidecomment (i, j) {
  el = document.getElementById ('comment-' + i + '-' + j);
  el.style.display = 'none';
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

function KeyedThing (key, title, thing, extras) {
  this.key = key;
  this.title = title;
  this.thing = thing;
  this.extras = extras;
}
intre = /^-?\d+%?$/;
function lowercmp (s1, s2) {
  t1 = s1.toLowerCase();
  t2 = s2.toLowerCase();
  if (t1 < t2)
    return -1;
  else if (t2 < t1)
    return 1;
  else
    return 0;
}
function titlecmp (thing1, thing2) {
  k1 = thing1.title;
  k2 = thing2.title;
  if (k1 == k2)
    return 0;
  else if (k1 == null)
    return 1;
  else if (k2 == null)
    return -1;
  else
    return lowercmp(k1, k2);
}
function keycmp (thing1, thing2) {
  k1 = thing1.key;
  k2 = thing2.key;
  if (k1 == k2)
    return titlecmp (thing1, thing2)
  else if (k1 == null)
    return 1;
  else if (k2 == null)
    return -1;
  else if (intre.exec(k1) && intre.exec(k2)) {
    n1 = parseInt(k1);
    n2 = parseInt(k2);
    return n2 - n1;
  }
  else
    return lowercmp(k1, k2);
  return 0;
}
function sort (tag, cls, key) {
  var things = []
  var els = document.getElementsByTagName (tag);

  for (var i = 0; i < els.length; i++) {
    el = els[i];
    if (has_class (el, cls)) {
      var extras = [];
      if (tag == 'dt') {
        dd = el.nextSibling;
        while (dd) {
          if (dd.nodeType == 1) {
            if (dd.tagName == 'DD') {
              extras.push (dd);
            } else {
              break;
            }
          }
          dd = dd.nextSibling;
      }}

      var el_key = null;
      var el_title = null;
      var these = Array.concat ([el], extras);
      for (var j = 0; j < these.length; j++) {
        var thisel = these[j];
        var spans = thisel.getElementsByTagName ('span');

        for (var k = 0; k < spans.length; k++) {
          if (has_class (spans[k], key)) {
            el_key = spans[k].innerHTML;
            break;
          }
          else if (has_class (spans[k], 'title')) {
            el_title = spans[k].innerHTML;
          }
        }
      }

      if (el_key == null) {
        el.className = el.className + ' nokey';
      }
      else if (has_class (el, 'nokey')) {
        oldcls = el.className.split(' ');
        newcls = [];
        for (var ci = 0; ci < oldcls.length; ci++) {
          if (oldcls[ci] != 'nokey') {
            newcls.push(oldcls[ci])
          }
        }
        el.className = newcls.join(' ');
      }
      keyed = new KeyedThing (el_key, el_title, el, extras);
      things.push (keyed);
    }
  }
  dummies = []
  for (var i = 0; i < things.length; i++) {
    dummy = document.createElement (tag);
    dummies.push (dummy);
    for (var j = 0; j < things[i].extras.length; j++) {
      var ex = things[i].extras[j];
      ex.parentNode.removeChild (ex);
    }
    things[i].thing.parentNode.replaceChild (dummy, things[i].thing);
  }
  things.sort (keycmp);
  for (var i = 0; i < things.length; i++) {
    dummies[i].parentNode.replaceChild (things[i].thing, dummies[i]);
    for (var j = 0; j < things[i].extras.length; j++) {
      things[i].thing.parentNode.insertBefore (things[i].extras[j], things[i].thing.nextSibling);
    }
  }
  td = document.getElementById ('slink-' + cls);
  for (var i = 0; i < td.childNodes.length; i++) {
    child = td.childNodes[i];
    if (child.className == 'slink') {
      if (child.id == ('slink-' + tag + '-' + cls + '-' + key)) {
        if (child.tagName == 'A') {
          span = document.createElement('span');
          span.id = child.id;
          span.className = child.className;
          span.innerHTML = child.innerHTML;
          child.parentNode.replaceChild (span, child);
        }
      }
      else {
        if (child.tagName == 'SPAN') {
          a = document.createElement('a');
          a.id = child.id;
          a.className = child.className;
          a.innerHTML = child.innerHTML;
          dat = child.id.split('-');
          a.href = 'javascript:sort(\'' + dat[1] + '\', \'' + dat[2]+ '\', \'' + dat[3] + '\')'
          child.parentNode.replaceChild (a, child);
        }
      }
    }
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
