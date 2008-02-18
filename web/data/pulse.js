/******************************************************************************/
/** Graph comments **/

function comment (i, j, x) {
  /* I'm not using JQuery here, because it's fairly trivial to do
   * what I'm doing, and because there was a noticeable lag when
   * I was using JQuery.  Perhaps a better JQuery programmer could
   * make it better, but this works perfectly.
   */
  var el = document.getElementById ('comment-' + i + '-' + j);
  if (el.style.display != 'block') {
    if (el.style.left == '') {
      var left = get_offsetLeft (document.getElementById('graph-' + i)) + x - 10;
      el.style.left = left + 'px';
    }
    el.style.display = 'block';
  } else {
    el.style.display = 'none';
  }
}


/******************************************************************************/
/** Expanders **/

function expander (id) {
  var div = $('#' + id + ' .exp-content');
  div.slideToggle('fast', function () {
    var open = div.css('display') != 'none';

    var img = $('#img-' + id);
    if (open)
      img.attr('src', img.attr('src').replace('closed', 'open'))
    else
      img.attr('src', img.attr('src').replace('open', 'closed'))

    var slinks = $('#slink-' + id).parent();
    if (slinks.length > 0) {
      var mask = $('#slink-' + id + '-mask');
      if (open) {
        mask.fadeOut();
      } else {
        if (mask.length == 0) {
          slinks.prepend ('<div id="slink-' + id + '-mask" class="mask"></div>');
          mask = $('#slink-' + id + '-mask');
          mask.css ('height', slinks.height() + 'px');
          mask.css ('width', slinks.width() + 'px');
        }
        mask.fadeIn();
      }
    }
  });
}


/******************************************************************************/
/** Replace Content **/

function replace (id, url) {
  var el = $('#' + id);
  var par = el.parents('.info-content');
  if (par.length > 0) {
    par.before ('<div class="infomask" id="infomask' + id + '">')
    var mask = $('#infomask' + id);
    mask.css ('height', par.height() + 'px');
    mask.css ('width', par.width() + 'px');
    mask.fadeIn('fast');
  }
  $.get(url, function (data) {
    if (document.createRange) {
      range = document.createRange();
      range.selectNode(el[0]);
      el[0].parentNode.replaceChild(range.createContextualFragment(data), el[0]);
    } else {
      el[0].outerHTML = data;
    }
    mask.fadeOut('fast', function () { mask.remove() })
  });
}


/******************************************************************************/
/** Popup links **/

function plink (id) {
  var plink = $('#plink' + id);
  var pcont = $('#pcont' + id);
  pcont.fadeIn('fast');
  var bot = pcont.offset().top + pcont.height();
  if (bot > window.innerHeight) {
    var newy;
    if (pcont.height() > window.innerHeight)
      newy = pcont.offset().top;
    else
      newy = bot - window.innerHeight + 10;
    if (newy > window.pageYOffset)
      window.scrollTo (0, newy);
  }
  var away = function (e) {
    var e = e || window.event;
    var target = e.target || e.srcElement;
    do {
      if (target == pcont[0])
        break;
      if (target == plink[0])
        break;
    } while (target = target.parentNode);
    if (target != pcont[0]) {
      pcont.fadeOut('fast');
      $('body').unbind('click', away);
      return (target != plink[0]);
    }
  }
  $('body').click (away);
}


/******************************************************************************/
/** Menu links **/

function mlink (id) {
  var mcont = $('#mcont' + id);
  var mlink = $('#mlink' + id);

  var show = function (mcont) {
    var pcont = mlink.parents('.pcont');
    if (pcont.length > 0)
      mcont.css ('left', mlink.offset().left - pcont.offset().left - 5 + 'px');
    else
      mcont.css ('left', mlink.offset().left - 5 + 'px');
    mcont.fadeIn('fast');
    var bot = mcont.offset().top + mcont.height();
    if (bot > window.innerHeight) {
      var newy;
      if (mcont.height() > window.innerHeight)
        newy = mcont.offset().top;
      else
        newy = bot - window.innerHeight + 10;
      if (newy > window.pageYOffset)
        window.scrollTo (0, newy);
    }
    var away = function (e) {
      var e = e || window.event;
      var target = e.target || e.srcElement;
      do {
        if (target == mcont[0])
          break;
        if (target == mlink[0])
          break;
      } while (target = target.parentNode);
      if (target != mcont[0]) {
        mcont.fadeOut('fast');
        $('body').unbind('click', away);
        return (target != mlink[0]);
      }
    }
    $('body').click (away);
  }

  if (mcont.hasClass('mstub')) {
    mlink.prepend ('<div id="mlink-' + id + '-mask" class="mask"></div>');
    var mask = $('#mlink-' + id + '-mask');
    mask.css ('height', mlink.height() + 'px');
    mask.css ('width', mlink.width() + 'px');
    mask.css ('background-color', mlink.parent().css('background-color'));
    mask.fadeIn('fast');
    $.get(mcont.html(), function (data) {
      if (document.createRange) {
        range = document.createRange();
        range.selectNode(mcont[0]);
        mcont[0].parentNode.replaceChild(range.createContextualFragment(data), mcont[0]);
      } else {
        mcont[0].outerHTML = data;
      }
      var cont = $('#mcont' + id);
      show(cont);
      mask.fadeOut('fast');
    });
  } else {
    show(mcont);
  }
}


/******************************************************************************/
/** FIXME **/

function keyedThing (key, title, thing, extras) {
  this.key = key;
  this.title = title;
  this.thing = thing;
  this.extras = extras;
}
intre = /^-?\d+%?$/;
function lowerCmp (s1, s2) {
  t1 = s1.toLowerCase();
  t2 = s2.toLowerCase();
  if (t1 < t2)
    return -1;
  else if (t2 < t1)
    return 1;
  else
    return 0;
}
function titleCmp (thing1, thing2) {
  k1 = thing1.title;
  k2 = thing2.title;
  if (k1 == k2)
    return 0;
  else if (k1 == null)
    return 1;
  else if (k2 == null)
    return -1;
  else
    return lowerCmp(k1, k2);
}
function keyCmp (thing1, thing2) {
  k1 = thing1.key;
  k2 = thing2.key;
  if (k1 == k2)
    return titleCmp (thing1, thing2)
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
    return lowerCmp(k1, k2);
  return 0;
}
function sort (tag, cls, key) {
  var things = [];

  var els = $(tag + '.' + cls);
  els.each (function () {
    var extras = []
    if (tag == 'dt') {
      /* FIXME: do this with jquery */
      dd = this.nextSibling;
      while (dd) {
        if (dd.nodeType == 1) {
          if (dd.tagName == 'DD') {
            extras.push (dd);
          } else {
            break;
          }
        }
        dd = dd.nextSibling;
      }
    }
  });
  return;
}
/*
  for (var i = 0; i < els.length; i++) {
    el = els[i];
    if (has_class (el, cls)) {
      var extras = [];
      if (tag == 'dt') {
        dd = el.nextSibling;
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
      keyed = new keyedThing (el_key, el_title, el, extras);
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
  things.sort (keyCmp);
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
*/


/******************************************************************************/

function has_class (el, cls) {
  var el_cls = el.className.split(' ');
  for (var i = 0; i < el_cls.length; i++) {
    if (cls == el_cls[i]) {
      return true;
    }
  }
  return false;
}

function get_offsetLeft (el) {
  left = 0;
  do {
    left += el.offsetLeft;
  } while (el = el.offsetParent);
  return left;
}

function get_offsetTop (el) {
  top = 0;
  do {
    top += el.offsetTop;
  } while (el = el.offsetParent);
  return top;
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

