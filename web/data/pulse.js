/******************************************************************************/
/** Masks **/
$.fn.mask = function (speed, options) {
  this.each(function () {
    var el = $(this);
    if (el.data('pulsemask') != undefined) { return; }
    var pulsemask = $('<div class="mask"></div>');
    var offset = el.offset();
    pulsemask.css({
      top: offset.top,
      left: offset.left,
      height: el.height(),
      width: el.width()
,backgroundColor: 'red'
    });
    if (options != undefined) {
      if (options.onclick != undefined) {
        pulsemask.click(options.onclick);
      }
    }
    pulsemask.resize_handler = function () {
      pulsemask.css({
        top: offset.top,
        left: offset.left,
        height: el.height(),
        width: el.width()
      });
    };
    $(window).bind('resize', pulsemask.resize_handler);
    pulsemask.hide();
    pulsemask.appendTo($('body'));
    pulsemask.fadeIn(speed);
    el.data('pulsemask', pulsemask);
  });
  return this;
};

$.fn.unmask = function (speed) {
  this.each(function () {
    var el = $(this);
    var pulsemask = el.data('pulsemask');
    if (pulsemask != undefined) {
      $(window).unbind('resize', pulsemask.resize_handler);
      pulsemask.fadeOut(speed, function () {
        pulsemask.remove();
        el.removeData('pulsemask');
      });
    }
  });
  return this;
};


/******************************************************************************/
/** Zoom images **/

function init_zoom (ctxt) {
  $('a.zoom', ctxt).click(function () {
    $('body').mask('fast', {
      onclick: function () {
        $('body').unmask('fast');
        $('div.zoom').fadeOut('fast', function () { $('div.zoom').remove() });
      }
    });
    var link = $(this);
    var img = new Image();
    img.src = link.attr('href');
    var open = function () {
      var zoomdiv = $('<div class="zoom"><img src="' + img.src + '"></div>');
      zoomdiv.appendTo('body');
      zoomdiv.css({
        top: link.offset().top,
        left: ((window.innerWidth - zoomdiv.width()) / 2) - 22,
        zIndex: 20
      });
      zoomdiv.fadeIn('fast', function () {
        scroll(zoomdiv, 40);
      });
    }
    if (img.complete) {
      open(link, img);
    } else {
      img.onload = function () { open(link, img) };
    }
    return false;
  })
}

$(document).ready(function() { init_zoom($(document)) });


/******************************************************************************/
/** AJAX boxes **/

$(document).ready(function () {
  $('.ajax').each(function (i) {
    var div = $(this);
    var link = $('a', div);
    var href = link.attr('href');
    var msg = div.text();
    var src = $('img', div).attr('src');
    div.empty();
    var process = function (adiv) {
      if (adiv.hasClass('stop')) {
        clearInterval(div.timer);
        div.remove();
      } else {
        var cur = adiv.current;
        var next = cur.next('img');
        if (next.length == 0)
          next = adiv.children('img:first-child');
        cur.css('display', 'none');
        next.css('display', 'inline');
        adiv.current = next;
      }
    };
    var base = src.substring(0, src.length - 6);
    for (var num = 0; num <= 35; num++) {
      var url = base;
      if (num < 10)
        url = url + '0';
      $('<img src="' + url + num + '.png">').css('display', 'none').appendTo(div);
    }
    div.append(' ' + msg);
    div.current = div.children('img:first-child');
    div.current.css('display', 'inline');
    div.timer = setInterval(function () { process(div); }, 80);
    div.slideDown('fast');
    $.get(href, {}, function (data) {
      var cont = $(data).css('display', 'none');
      cont.insertAfter(div);
      div.slideUp('fast', function () { div.addClass('stop'); });
      cont.slideDown('fast');
    });
  });
});


/******************************************************************************/
/** Graph slides **/

function slide (id, dir) {
  var div = $('#graph-' + id);
  if (div[0].timer != undefined) {
    return;
  }
  var curimg = div.children('img');
  var width = curimg.width();
  div.css({
    width: width,
    height: curimg.height()
  });
  var cursrc = curimg.attr('src');
  var newdata = slidecalc(cursrc, dir);
  var newsrc = newdata.src;
  var newmapid = 'graphmap' + id + '-' + newdata.num;
  var newmap = $('#' + newmapid);
  if (newmap.length == 0) {
    var filename = newdata.filename;
    var graphurl = window.location + '?ajax=graphmap&id=' + id + '&num=' + newdata.num + '&filename=' + filename;
    $.get(graphurl, function (data) {
      div.append(data);
    });
  }

  if (dir == -1) {
    var nextlink = $('#graphprev-' + id);
    var backlink = $('#graphnext-' + id);
  } else {
    var nextlink = $('#graphnext-' + id);
    var backlink = $('#graphprev-' + id);
  }
  backlink.unmask();

  var nextsrc = slidecalc(newsrc, dir).src;
  if (nextsrc == undefined) {
    nextlink.mask();
  } else {
    var nextimg = new Image();
    nextimg.src = nextsrc;
    if (!nextimg.complete) {
      nextlink.mask();
      nextimg.onload = function () { nextlink.unmask(); };
    }
  }

  var slidego = function () {
    curimg.wrap('<div class="graphaway"></div>'); 
    curdiv = $('div.graphaway', div);
    curdiv.css({
      top: curdiv.offset().top
    });
    newimg = $('<img src="' + newsrc + '" usemap="#' + newmapid + '" ismap>');
    newimg.css({
      marginLeft: dir * width
    });
    curleft = curdiv.offset().left;
    curdiv.css({
      left: curleft
    });
    curdiv.iter = 0;
    var slideiter = function () {
      curdiv.iter += 3;
      if (curdiv.iter > width) { curdiv.iter = width; }
      curdiv.css({
        width: (width - curdiv.iter)
      });
      if (dir == -1) {
        curdiv.css({
          left: curleft + curdiv.iter
        });
      } else {
        curimg.css({
          marginLeft: -curdiv.iter
        });
      }
      newimg.css({
        marginLeft: (dir * (width - curdiv.iter))
      });
      if (curdiv.iter == width) {
        clearInterval(div[0].timer);
        div[0].timer = undefined;
        curdiv.remove();
      }
    };
    if (dir == -1) {
      newimg.prependTo(div);
    } else {
      newimg.appendTo(div);
    }
    div[0].timer = setInterval(slideiter, 1);
  };

  var img = new Image();
  img.src = newsrc;
  if (img.complete) {
    slidego();
  } else {
    img.onload = slidego;
  }
}

function slidecalc(src, dir) {
  var re = /^(.*)\/([^\/]*-)(\d+)\.png$/
  var match = re.exec (src);
  var base = match[1]
  var filename = match[2];
  var curnum = match[3];
  var newnum = parseInt(curnum) - dir;
  if (newnum < 0) {
    return {filename: undefined, src: undefined, num: undefined};
  }
  filename = filename + newnum + '.png';
  var newsrc = base + '/' + filename;
  return {
    filename: filename,
    src: newsrc,
    num: newnum
  };
}

$(document).ready(function() {
  var nexts = $('a.graphnext');
  nexts.mask();
  var prevs = $('a.graphprev');
  prevs.each(function () {
    var thisq = $(this);
    thisq.css('visibility', 'visible');
    thisq.mask();
    var re = /^.*-(\d+)$/
    var match = re.exec(thisq.attr('id'));
    var id = match[1];
    var div = $('#graph-' + id)
    var img = div.children('img');
    var newsrc = slidecalc(img.attr('src'), -1).src;
    var newimg = new Image();
    newimg.src = newsrc;
    if (newimg.complete) {
      thisq.unmask();
    } else {
      newimg.onload = function () { thisq.unmask(); };
    }
  });
});


/******************************************************************************/
/** Graph comments **/

function comment (count, num, j, x) {
  var el = $('#comment-' + count + '-' + num + '-' + j);
  if (el.css('display') != 'block') {
    var graph = $('#graph-' + count);
    var offset = graph.offset();
    el.css({
      left: offset.left + x - 10,
      top: offset.top + graph.height(),
      zIndex: 20
    });
    el.css('display', 'block');
  } else {
    el.css('display', 'none');
  }
}


/******************************************************************************/
/** Expanders **/

function expander (id) {
  var div = $('#' + id + ' .exp-content');
  div.slideToggle('fast', function () {
    var open = div.is(':visible');

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
/** Info Boxes **/

function info (id) {
  var div = $('#' + id).children('.info-content').children('div');
  div.slideToggle('fast', function () {
    var img = $('#infoimg-' + id);
    if (div.is(':visible'))
      img.attr('src', img.attr('src').replace('up', 'open'))
    else
      img.attr('src', img.attr('src').replace('open', 'up'))
  });
}


/******************************************************************************/
/** Ellipsized text **/

function ellip (id) {
  $('#elliplnk-' + id).remove();
  $('#elliptxt-' + id).fadeIn('fast');
}


/******************************************************************************/
/** Replace Content **/

function replace (id, url) {
  var el = $('#' + id);
  var par = el.parents('.info-content');
  if (par.length > 0) {
    par.before ('<div class="infomask" id="infomask' + id + '"></div>')
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
/** Automatic scrolling **/
function scroll (div, pad) {
  var bot = div.offset().top + div.height();
  if (!pad)
    var pad = 20;
  if (bot > window.innerHeight) {
    var newy;
    if (div.height() > window.innerHeight)
      newy = div.offset().top;
    else
      newy = bot - window.innerHeight + pad;
    if (newy > window.pageYOffset)
      for (var i = window.pageYOffset; i <= newy; i += 2)
        window.scrollTo(0, i);
  }
}


/******************************************************************************/
/** Popup links **/

function plink (id) {
  var plink = $('#plink' + id);
  var pcont = $('#pcont' + id);
  pcont.fadeIn('fast');
  scroll(pcont);
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
        newy = bot - window.innerHeight + 20;
      if (newy > window.pageYOffset)
        for (var i = window.pageYOffset; i <= newy; i += 2)
          window.scrollTo (0, i);
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
/** Sort links **/

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
  els.each (function (el) {
    var el = $(this);
    var extras = [];
    if (el.is('dt')) {
      dd = el;
      while ((dd = dd.next()).is('dd'))
        extras.push(dd[0]);
    }

    var el_key = null;
    var el_title = null;
    var these = Array.concat (el[0], extras);
    for (var j = 0; j < these.length; j++) {
      var par = $(these[j]);
      var spans = par.find('span');
      spans.each(function () {
        var span = $(this);
        if (span.hasClass(key))
          el_key = span.html()
        else if (span.hasClass('title'))
          el_title = span.html()
      });
    }
    if (el_key == null)
      el.addClass('nokey');
    else
      el.removeClass('nokey');
    var keyed = new keyedThing (el_key, el_title, el[0], extras);
    things.push(keyed);
  });

  var dummies = [];
  for (var i = 0; i < things.length; i++) {
    var dummy = document.createElement(tag);
    dummies.push(dummy);
    for (var j = 0; j < things[i].extras.length; j++) {
      var ex = things[i].extras[j];
      ex.parentNode.removeChild(ex);
    }
    things[i].thing.parentNode.replaceChild(dummy, things[i].thing);
  }

  things.sort(keyCmp);
  for (var i = 0; i < things.length; i++) {
    dummies[i].parentNode.replaceChild(things[i].thing, dummies[i]);
    for (var j = 0; j < things[i].extras.length; j++)
      things[i].thing.parentNode.insertBefore(things[i].extras[j], things[i].thing.nextSibling);
  }

  var slinks = $('#slink-' + cls);
  slinks.find('.slink').each(function () {
    var slink = $(this);
    if (slink.is('#slink-' + tag + '-' + cls + '-' + key)) {
      if (slink.is('a')) {
        var span = document.createElement('span');
        span.id = slink[0].id;
        span.className = slink[0].className;
        span.innerHTML = slink.html();
        slink[0].parentNode.replaceChild(span, slink[0]);
      }
    }
    else {
      if (slink.is('span')) {
        var a = document.createElement('a');
        a.id = slink[0].id
        a.className = slink[0].className;
        a.innerHTML = slink.html();
        dat = slink[0].id.split('-');
        a.href = 'javascript:sort(\'' + dat[1] + '\', \'' + dat[2]+ '\', \'' + dat[3] + '\')'
        slink[0].parentNode.replaceChild(a, slink[0]);
      }
    }
  });
}


/******************************************************************************/
/** Utility functions **/

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
