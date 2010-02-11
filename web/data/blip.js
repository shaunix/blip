/******************************************************************************/
/** Debug **/
function debug (txt) {
  dbg = $('div#debug');
  if (dbg.length == 0) {
    $('body').append ('<div id="debug"></div>')
    dbg = $('div#debug');
    dbg.css ({
      position: 'absolute',
      top: 40,
      right: 40,
      padding: '2px 1em 2px 1em',
      backgroundColor: '#eeeeec',
      border: 'solid 2px #ef2929',
      opacity: 0.1,
    });
    dbg.hover (
      function () { $(this).css({opacity: 1.0}) },
      function () { $(this).css({opacity: 0.1}) }
    );
  }
  var div = $('<div></div>');
  div.text (txt);
  dbg.append (div);
}


/******************************************************************************/
/** On-screen slide toggling **/

$.fn.onScreenSlideToggle = function (speed) {
  var div = $(this);
  var visible = div.is(':visible');
  if (visible) {
    var height = div.height();
    div.data ('height', height);
  } else {
    var height = div.data ('height');
    div.removeData ('height');
    div.css ({display: 'block'});
  }
  var diff = (height + div.offset().top) - (window.pageYOffset + window.innerHeight);
  if (visible) {
    if (diff > 0)
      div.css ({overflow: 'hidden', height: height - diff});
    div.slideUp (200);
  } else {
    div.css ({display: 'none'});
    div.slideDown (200, function () {
      if (diff > 0)
        div.css ({overflow: 'visible', height: height});
      else
        div.animate ({height: height}, 200, function () {
          div.css ({overflow: 'visible'});
        });
    });
  }
};


/******************************************************************************/
/** Shading **/

$.fn.shade = function (speed, options) {
  this.each(function () {
    var el = $(this);
    links = el.find('a').andSelf('a');
    links.each(function () {
      var link = $(this);
      link.data('href', link.attr('href'));
      link.data('onclick', link.attr('onclick'));
      link.removeAttr('href');
    });
    imgs = el.find('img');
    imgs.each(function () {
      var img = $(this);
      if (img.attr('usemap') != undefined) {
        img.data('usemap', img.attr('usemap'));
        img.removeAttr('usemap');
      }
    });
    el.animate({opacity: 0.4}, 400);
  });
  return this;
};

$.fn.unshade = function (speed) {
  this.each(function () {
    var el = $(this);
    links = el.find('a').andSelf('a');
    links.each(function () {
      var link = $(this);
      link.attr('href', link.data('href'));
      link.attr('onclick', link.data('onclick'));
    });
    imgs = el.find('img');
    imgs.each(function () {
      var img = $(this);
      if (img.data('usemap') != undefined) {
        img.attr('usemap', img.data('usemap'));
      }
    });
    el.animate({opacity: 1.0}, 400);
  });
  return this;
};


/******************************************************************************/

$.fn.pulse_init = function () {
  /** Forms **/
  var pass1 = null;
  var pass2 = null;
  this.find ('input').each (function () {
    var input = $(this);
    if (input.attr ('name') == 'password1')
      pass1 = input;
    else if (input.attr ('name') == 'password2')
      pass2 = input;
    input.focus (function () { $(this).addClass ('inputactive'); });
    input.blur (function () { $(this).removeClass ('inputactive'); });
  });
  if (pass1 != null && pass2 != null) {
    var linker = $('<div id="passwordlinker"></div>');
    var ltop = Math.floor(pass1.offset().top + (pass1.height() / 2));
    var lbot = Math.floor(pass2.offset().top + (pass2.height() / 2));
    linker.css ({
      position: 'absolute',
      borderRight: 'solid 1px #888a85',
      borderTop: 'solid 1px #888a85',
      borderBottom: 'solid 1px #888a85',
      left: pass1.offset().left + pass2.width() + 6,
      top: ltop,
      height: lbot - ltop,
      lineHeight: lbot - ltop,
      width: 12
    });
    $('body').append(linker);
    var img = $('<img id="passworderror" src="' + pulse_data + 'admon-error-16.png">')
    img.css ({
      position: 'absolute',
      left: pass1.offset().left + pass2.width() + 10,
      top: ltop + ((lbot - ltop - 16) / 2) + 1,
    });
    img.hide ();
    $('body').append(img);
    var onchange = function () {
      if (pass1.attr('value') == pass2.attr('value')) {
        $('#passworderror').fadeOut ('fast');
        $('#create')[0].disabled = false;
      } else {
        $('#passworderror').fadeIn ('fast');
        $('#create')[0].disabled = true;
      }
    };
    pass1.keyup (onchange);
    pass2.keyup (onchange);
  }

  /** AJAX Boxes **/
  this.find ('.ajax').each(function (i) {
    var div = $(this);
    var link = $('a', div);
    var href = link.attr('href');

    div.empty();
    div.show();

    var thr = throbberbar();
    thr.css('width', div.width() - 20);
    div.append (thr);
    thr.start ();

    $.ajax({
      url: href, 
      complete: function (req, status) {
        var cont = $(req.responseText).css('display', 'none');
        cont.insertAfter(div);
        thr.stop ();
        div.remove ();
        cont.pulse_init ();
        cont.slideDown('fast');
      }
    });
  });

  /** Info Boxes **/
  this.find ('div.info').each (function () {
    var div = $(this);
    div.children ('div.infotitle').click (function () {
    var active = div.hasClass ('infoactive');
    $('div.info').each (function () {
      $this = $(this).removeClass('infoactive')
      $this.find('div.sortmenu').hide();
      $this.find('div.sortlinks').slideUp('fast');
      $this.find('div.lboxdesc').slideUp('fast');
      $this.find('div.filters').slideUp('fast');
      $this.find('table.facts').slideUp('fast');
      $this.find('dd').slideUp('fast');
    });
    if (!active) {
      div.addClass ('infoactive');
      div.find('div.sortlinks').slideDown('fast');
      div.find('div.lboxdesc').slideDown('fast');
      div.find('div.filters').slideDown('fast');
      div.find('table.facts').slideDown('fast');
      div.find('dd').slideDown('fast');
    }
    });
  });

  /** Calendars **/
  this.find ('div.cal').each (function () {
    var cal = $(this);
    cal_display (cal);
    cal.find ('td.calprev').click (function () { cal_prev (cal); });
    cal.find ('td.calnext').click (function () { cal_next (cal); });
    cal.find ('dt.calevent').each (function () {
      var dt = $(this);
      dt.next('dd').andSelf('dt').hover (
        function () {
          var daynum = parseInt (dt.children('span.caldtstart').text().substr(8));
          cal.find ('td.calday').each (function () {
            var day = $(this);
            if (day.hasClass ('caldayoff'))
              return;
            if (parseInt(day.text()) == daynum)
              day.addClass ('calhover');
          });
        },
        function () {
          cal.find ('td.calday').removeClass ('calhover');
        }
    )});
  });

  /** Zoom Images **/
  this.find ('a.zoom').click(function () {
    var mask = $('<div class="mask"></div>');
    var body = $('body');
    var maskresize = function () {
      var offset = body.offset();
      mask.css({
        top: offset.top,
        left: offset.left,
        position: 'fixed',
        height: window.innerHeight,
        width: window.innerWidth
      });
    };
    maskresize();
    $(window).bind('resize', maskresize);
    mask.click(function () {
      $(window).unbind('resize', maskresize)
      mask.fadeOut('fast', function () { mask.remove(); });
      $('div.zoom').fadeOut('fast', function () { $('div.zoom').remove() });
    });
    mask.hide();
    mask.appendTo(body);
    mask.show();
    var link = $(this);
    var img = new Image();
    img.src = link.attr('href');
    var open = function () {
      var zoomdiv = $('<div class="zoom"><img src="' + img.src + '"></div>');
      zoomdiv.appendTo('body');
      zoomdiv.css({
        top: ((window.innerHeight - zoomdiv.height()) / 2),
        left: ((window.innerWidth - zoomdiv.width()) / 2) - 22,
        zIndex: 20
      });
      zoomdiv.show();
    }
    if (img.complete) {
      open(link, img);
    } else {
      img.onload = function () { open(link, img) };
    }
    return false;
  });

  /** Expanders **/
  this.find ('.contexp').click (function () { 
    var lnk = $(this);
    var par = $(this).parents ('table.cont:first');
    var cont = par.find ('div.cont-content:first');
    var open = cont.is (':visible');

    if (open)
      par.find ('td.contexp:first').html ('&#9656;');
    else
      par.find ('td.contexp:first').html ('&#9662;');

    var slinks = par.find ('div.sortlinks:first');
    if (slinks.length > 0) {
      if (open)
        slinks.shade();
      else
        slinks.unshade();
    }

    cont.onScreenSlideToggle ();
  });

  /** Ellipsized Labels **/
  this.find ('span.elliptxt').each (function () {
    var span = $(this);
    var lnk = $('<a class="elliplnk">(more)</a>');
    lnk.click (function () {
      lnk.remove ();
      span.fadeIn ('fast');
    });
    span.hide ();
    span.before (lnk);
  });

  /** Graph Slides **/
  var nexts = this.find ('a.graphnext');
  nexts.shade();
  var prevs = this.find ('a.graphprev');
  prevs.each(function () {
    var thisq = $(this);
    thisq.css('visibility', 'visible');
    thisq.shade();
    var re = /^.*-(\d+)$/
    var match = re.exec(thisq.attr('id'));
    var id = match[1];
    var div = $('#graph-' + id)
    var img = div.children('img');
    var newsrc = slidecalc(img.attr('src'), -1).src;
    $.ajax({
      url: newsrc,
      success: function () {
        thisq.unshade();
    }});
  });

  /** Sort Menus **/
  this.find ('span.sortlinks').each (function () {
    var links = $(this);
    var div = links.parent ('div.sortlinks');
    var id = div.attr ('id').substr (11);
    links.click (function () {
      var container = $('#' + id);
      var menu = container.find ('#sortmenu__' + id);
      menu.css ({
        top: div.offset().top + div.height(),
        right: $(document).width() - (div.offset().left + div.width())
      });
      var away = function (e) {
        var e = e || window.event;
        var target = e.target || e.srcElement;
        do {
          if (target == links[0])
            break;
          if (target == menu[0])
            break;
        } while (target = target.parentNode);
        if (target != menu[0]) {
          links.removeClass ('sortlinksactive');
          menu.hide ();
          $('body').unbind('click', away);
          return (target != div[0]);
        }
      }
      menu.data('awayfunc', away);
      links.addClass ('sortlinksactive');
      $('body').click (away);
      menu.show ();
      return false;
    })
  });

  /** Graph Maps **/
  if (this.is ('img.graphmap'))
    var graphmaps = this;
  else
    var graphmaps = this.find ('img.graphmap');
  graphmaps.each (function () {
    var graphmap = $(this);
    var dat = graphmap.attr('id').split('-');
    var count = dat[1];
    var num = dat[2];
    var target = $('#graphtarget-' + count);
    var div = $('div#graph-' + count);
    if (target.length == 0) {
      div.append ('<a class="graphtarget" id="graphtarget-' + count + '"></a>');
      target = $('#graphtarget-' + count);
      div.bind ("mouseleave", function () {
        target.fadeOut ('fast');
        div.find ('.comment').fadeOut ('fast');
      });
    }
    graphmap.mousemove (function (e) {
      var offset = graphmap.offset();
      var i = e.clientX - offset.left;
      var comment;
      while (i >= 0) {
        comment = $('#comment-' + count + '-' + num + '-' + i);
        if (comment.length > 0)
          break;
        i -= 1;
      }
      if (comment.length != 1)
        return;
      if (comment.is (':hidden')) {
        div.find ('.comment').css ('display', 'none');
        comment.css ({
          left: offset.left + i,
          top: offset.top + graphmap.height() + 1,
          zIndex: 20,
          display: 'block'
        });
        target.attr ('href', comment.attr('href'));
        target.css ({
          top: offset.top,
          left: offset.left + i,
          height: graphmap.height(),
          lineHeight: graphmap.height(),
          width: 4,
          display: 'block'
        });
        target.blur();
      }
    });
  });
}

$(document).ready (function () { $('html').pulse_init(); });


/******************************************************************************/
/** Tabs **/

function tab (tabid) {
  var tabbar = $('#tabs');
  var tabs = tabbar.children ('.tab');
  var curhash = '';
  if (location.hash != '')
    curhash = location.hash.substring(1);

  if (tabid == undefined) {
    if (curhash == '')
      tabid = tabbar[0].default_tabid;
    else
      tabid = curhash;
  }
  else {
    if (tabid == curhash || (curhash == '' && tabid == tabbar[0].default_tabid)) {
      if (tabbar[0].current_tabid != undefined) {
        oldpane = $('#pane-' + tabbar[0].current_tabid);
        oldpane.remove ();
      }
    }
    location.hash = '#' + tabid;
  }

  var oldpane = undefined;
  if (tabbar[0].current_tabid != undefined)
    oldpane = $('#pane-' + tabbar[0].current_tabid);
  if (oldpane != undefined)
    oldpane.hide();

  tabs.removeClass ('tabactive');
  var tab = $('#tab-' + tabid);
  tab.addClass ('tabactive');

  if (tabbar[0].current_tabid == undefined)
    document.title = document.title + ' - ' + tab.text();
  else
    document.title = document.title.substr(0, document.title.lastIndexOf(' - ') + 3) + tab.text();

  tabbar[0].current_tabid = tabid;
  var paneid = 'pane-' + tabid;
  var pane = $('#' + paneid);
  if (pane.length > 0) {
    if (pane.hasClass ('paneloading'))
      $('#reload').shade ();
    else
      $('#reload').unshade ();
    pane.show();
  } else {
    var panes = $('#panes');
    $('#reload').shade ();
    pane = $('<div class="pane"></div>');
    pane.attr ('id', paneid);
    pane.addClass ('paneloading');
    var thr = throbberbar();
    thr.css('width', panes.width() / 2);
    pane.append (thr);
    panes.append (pane);
    pane.show ();
    thr.start ();
    tabbar[0].loading_tabid = tabid;
    var href = pulse_url + '?q=tab&tab=' + tabid;
    var func = function (req, status) {
      var pane = $('#' + paneid);
      pane.html ($(req.responseText));
      pane.pulse_init ();
      pane.removeClass ('paneloading');
      if (tabid == tabbar[0].current_tabid) {
        thr.stop ();
        $('#reload').unshade ();
        tabbar[0].loading_tabid = undefined;
        pane.show ();
      }
    };
    $.ajax({url: href, complete: func});
  }
}

function reload () {
  var tabbar = $('#tabs');
  if (tabbar[0].current_tabid != undefined) {
    oldpane = $('#pane-' + tabbar[0].current_tabid);
    oldpane.remove ();
  }
  tab (tabbar[0].current_tabid);
}

$(document).ready (function () {
  var tabbar = $('#tabs');
  if (tabbar.length == 0)
    return;
  tabbar[0].default_tabid = tabbar.children('.tab').attr('id').substring(4);
  tab ();
  setInterval (function () {
    var tabbar = $('#tabs');
    var tabid = tabbar[0].current_tabid;
    if (tabid == undefined)
      return;
    if (location.hash == '' || location.hash == '#')
      if (tabid == tabbar[0].default_tabid)
        return;
    if ('#' + tabid != location.hash)
      tab ();
  }, 200);
});


/******************************************************************************/
/** Trobber **/

function throbberbar () {
  var div = $('<div class="throbberbar"><div></div></div>');
  var bar = div.children('div');
  var process = function () {
    var margin = parseInt (bar.css ('margin-left'));
    if (margin > div.width())
      bar.css('margin-left', -bar.width());
    else
      bar.css('margin-left', margin + 3);
  };
  div.start = function () { div.timer = setInterval (process, 20); }
  div.stop = function () {
    clearInterval (div.timer);
    div.remove ();
  }
  return div;
}


/******************************************************************************/
/** Calendars **/

function cal_display (cal, month, year) {
  var today = new Date ();
  if (month == undefined)
    month = today.getUTCMonth ();
  if (year == undefined)
    year = today.getUTCFullYear ();
  cal.find ('span.calyear').text (year);
  var calmonth = cal.find ('span.calmonth');
  calmonth.data ('monthnum', month);
  calmonth.text (
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December']
    [month]);
  var tds = cal.find ('td.calday');
  var events = cal.find ('span.caldtstart');
  events.parent().hide();
  events.parent().next('dd').hide();
  var firstday = new Date (year, month, 1)
  var weekday = firstday.getDay() || 7;
  var j = 0;
  for (var i = 1; i <= 42; i++) {
    thisday = new Date(year, month, i - weekday + 1);
    var td = tds.eq (i - 1);
    td.html ('<div>' + thisday.getDate () + '</div>');
    if (thisday.getFullYear() == today.getFullYear() &&
        thisday.getMonth() == today.getMonth() &&
        thisday.getDate() == today.getDate())
      td.addClass ('caltoday');
    else
      td.removeClass ('caltoday');
    var thisfull = thisday.getFullYear() + '-';
    if (thisday.getMonth() + 1 < 10)
      thisfull += '0';
    thisfull += (thisday.getMonth() + 1) + '-';
    if (thisday.getDate() < 10)
      thisfull += '0';
    thisfull += thisday.getDate();
    while ((j < events.length) && lowerCmp (events.eq(j).text(), thisfull, 1) < 0)
      j++;
    td.removeClass ('calevent');
    td.unbind ('click');
    if (thisday.getMonth() == firstday.getMonth()) {
      td.removeClass ('caldayoff');
      if (lowerCmp (events.eq(j).text(), thisfull, 1) == 0) {
        events.eq(j).parent().show();
        events.eq(j).parent().next('dd:first').show();
        td.addClass ('calevent');
      }
    } else {
      td.addClass ('caldayoff');
      if (thisday.getYear() > firstday.getYear())
        td.click (function () { cal_next(cal) });
      else if (thisday.getYear() < firstday.getYear())
        td.click (function () { cal_prev(cal) });
      else if (thisday.getMonth() > firstday.getMonth())
        td.click (function () { cal_next(cal) });
      else
        td.click (function () { cal_prev(cal) });
    }
  }
}

function cal_prev (cal) {
  var month = cal.find ('span.calmonth').data ('monthnum');
  var year = parseInt (cal.find ('span.calyear').text ());
  month--;
  if (month < 0) {
    month = 12 + month;
    year--;
  }
  cal_display (cal, month, year);
}

function cal_next (cal) {
  var month = cal.find ('span.calmonth').data ('monthnum');
  var year = parseInt (cal.find ('span.calyear').text ());
  month++;
  if (month > 11) {
    month = month - 12;
    year++;
  }
  cal_display (cal, month, year);
}


/******************************************************************************/
/** Graph slides **/

function slide (app, id, dir) {
  var div = $('#graph-' + id);
  if (div[0].timer != undefined) {
    return;
  }
  var curimg = div.children('img');
  var width = curimg.width();
  div.css({
    overflow: 'hidden',
    width: width,
    height: curimg.height()
  });
  var cursrc = curimg.attr('src');
  var newdata = slidecalc(cursrc, dir);
  var newsrc = newdata.src;
  var newcmt = $('#comments-' + id + '-' + newdata.num);
  if (newcmt.length == 0) {
    $.ajax ({
      type: 'GET',
      url: pulse_url,
      data: {'q': 'graphmap', 'graphmap': app, 'id': id,
             'num' : newdata.num, 'filename': newdata.filename},
      complete: function (req, status) {
        if (status == 'success') {
          div.append ($(req.responseText));
        }
      }
    });
  }

  if (dir == -1) {
    var nextlink = $('#graphprev-' + id);
    var backlink = $('#graphnext-' + id);
  } else {
    var nextlink = $('#graphnext-' + id);
    var backlink = $('#graphprev-' + id);
  }
  backlink.unshade();

  nextlink.shade();
  var nextsrc = slidecalc(newsrc, dir).src;
  if (nextsrc != undefined) {
    $.ajax({
      url: nextsrc,
      success: function () {
        nextlink.unshade();
    }});
  }

  var slidego = function () {
    curimg.wrap('<div class="graphaway"></div>'); 
    curdiv = $('div.graphaway', div);
    curdiv.css({
      top: curdiv.offset().top
    });
    var newimgid = 'graphmap-' + id + '-' + newdata.num;
    newimg = $('<img src="' + newsrc + '" class="graphmap" id="' + newimgid + '">');
    newimg.css({
      marginLeft: dir * width
    });
    curleft = curdiv.offset().left;
    curdiv.css({
      left: curleft
    });
    curdiv.iter = 0;
    var slideiter = function () {
      curdiv.iter += 6;
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
        div.css ({overflow: 'visible'});
        newimg.pulse_init ();
      }
    };
    if (dir == -1) {
      newimg.prependTo(div);
    } else {
      newimg.appendTo(div);
    }
    div[0].timer = setInterval(slideiter, 1);
  };

  $.ajax({
    url: newsrc,
    success: slidego
  });
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


/******************************************************************************/
/** Replace Content **/

function replace (id, url) {
  var el = $('#' + id);
  var par = el.parents('.infocont');
  if (par.length > 0) {
   par.shade();
  }
  el.empty ();
  var thr = throbberbar ();
  thr.css('width', el.width() / 2);
  el.append (thr);
  thr.start ();
  $.ajax ({
    type: 'GET',
    url: url,
    complete: function (req, status) {
      data = $(req.responseText);
      data.attr ('id', el.attr ('id'));
      el.after (data);
      el.remove ();
      par.unshade ();
    }
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
    mlink.shade();
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
      mlink.unshade();
    });
  } else {
    show(mcont);
  }
}


/******************************************************************************/
/** Filters **/

function filter (id, tag, cls, key) {
  $('a.filter-' + id).each (function () {
    var link = $(this);
    if (link.is('#filter__' + id + '___all')) {
      if (key == null)
        link.addClass ('filteron');
      else
        link.removeClass ('filteron');
    }
    else if (link.is('#filter__' + id + '__' + key))
      link.addClass ('filteron');
    else
      link.removeClass ('filteron');
  });
  $('#' + id).find (tag + '.' + cls).each (function () {
    var el = $(this);
    var show = false;
    if (key == null)
      show = true;
    else
      show = (el.find('img.badge-' + key).length > 0);
    if (!el.is(':visible') && show)
      el.slideDown ();
    else if (el.is(':visible') && !show)
      el.slideUp ();
  });
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
function lowerCmp (s1, s2, asc) {
  t1 = s1.toLowerCase();
  t2 = s2.toLowerCase();
  if (t1 < t2)
    return -asc;
  else if (t2 < t1)
    return asc;
  else
    return 0;
}
function titleCmp (thing1, thing2, asc) {
  k1 = thing1.title;
  k2 = thing2.title;
  if (k1 == k2)
    return 0;
  else if (k1 == null)
    return asc;
  else if (k2 == null)
    return -asc;
  else
    return lowerCmp(k1, k2, asc);
}
function keyCmp (thing1, thing2, asc) {
  k1 = thing1.key;
  k2 = thing2.key;
  if (k1 == k2)
    return titleCmp (thing1, thing2, 1)
  else if (k1 == null)
    return -asc;
  else if (k2 == null)
    return asc;
  else if (intre.exec(k1) && intre.exec(k2)) {
    n1 = parseInt(k1);
    n2 = parseInt(k2);
    return asc * (n1 - n2);
  }
  else
    return lowerCmp(k1, k2, asc);
  return 0;
}
function sort (id, tag, cls, key, asc) {
  var things = [];

  var container = $('#' + id);
  var els = container.find (tag + '.' + cls);
  els.each (function (el) {
    var el = $(this);
    var these = el;
    if (el.is('dt')) {
      dd = el;
      while ((dd = dd.next()).is('dd'))
        these = these.add(dd);
    }

    var el_key = these.find ('span.' + key);
    var el_title = these.find ('span.title');

    if (el_key.length > 0) {
      el_key = el_key.html();
      el.removeClass ('nokey');
    } else {
      el_key = null;
      el.addClass ('nokey');
    }

    if (el_title.length > 0)
      el_title = el_title.html();
    else
      el_title = null;

    var keyed = new keyedThing (el_key, el_title, el, these.slice(1));
    things.push(keyed);
  });

  var dummies = [];
  for (var i = 0; i < things.length; i++) {
    var dummy = $('<' + tag + '></' + tag + '>');
    dummies.push (dummy);
    things[i].extras.remove ();
    things[i].thing.replaceWith (dummy);
  }

  things.sort( function (a, b) { return keyCmp (a, b, asc); } );
  for (var i = 0; i < things.length; i++) {
    dummies[i].replaceWith (things[i].thing);
    things[i].thing.after (things[i].extras);
  }

  var links = $('#sortlinks__' + id);
  links.find('.sortlink').each(function () {
    var slink = $(this);
    if (slink.is('#sortlink__' + id + '__' + tag + '__' + cls + '__' + key + '__' + asc)) {
      if (slink.is('a')) {
        var span = $('<span></span>').attr ({
          'id': slink.attr ('id'),
          'class': slink.attr ('class')
        });
        span.html (slink.html());
        slink.replaceWith (span);
      }
    }
    else {
      if (slink.is('span')) {
        dat = slink.attr('id').split('__');
        var a = $('<a></a>').attr ({
          'id': slink.attr ('id'),
          'class': slink.attr ('class'),
          'href': 'javascript:sort(\'' + dat[1] + '\', \'' + dat[2] + '\', \'' + dat[3]+ '\', \'' + dat[4] + '\', ' + dat[5] + ')'
        });
        a.html (slink.html());
        slink.replaceWith (a);
      }
    }
  });
  curtxt = $('#sortlink__' + id + '__' + key).html();
  curtxt += (asc == 1) ? ' ▴' : ' ▾';
  links.find ('span.sortcur').html (curtxt);
  var menu = $('#sortmenu__' + id);
  $('body').unbind('click', menu.data('awayfunc'));
  links.children ('span.sortlinks').removeClass ('sortlinksactive');
  menu.hide();
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

/******************************************************************************/
/** Account Stuff **/

function createaccount () {
  var realname = $('#realname').attr('value');
  var username = $('#username').attr('value');
  var email = $('#email').attr('value');
  var pass1 = $('#password1').attr('value');
  var pass2 = $('#password2').attr('value');
  if (pass1 != pass2) {
    $('#passworderror').fadeOut ('fast', function () {
    $('#passworderror').fadeIn ('fast', function () {
    $('#passworderror').fadeOut ('fast', function () {
    $('#passworderror').fadeIn ('fast');
    }) }) });
    return;
  }
  $('input').blur().each (function () { this.disabled = true; });
  $.ajax ({
    type: 'POST',
    url: pulse_url + '?action=create',
    data: {'realname': realname, 'username': username, 'email': email, 'password': pass1},
    complete: function (req, status) {
      if (status == 'success') {
        $('#accountform').children ('form').remove ();
        $('#accountform').children ('.admon').remove ();
        $('#passwordlinker').remove ();
        $('#passworderror').remove ();
        $('#accountform').append(req.responseText);
      } else {
        $('#accountform').children ('.admon').remove ();
        $('#accountform').append(req.responseText);
        $('input').each (function () { this.disabled = false; });
      }
    }
  });
}

function watch (ident) {
  $.ajax ({
    type: 'GET',
    url: pulse_root + 'account',
    data: {'action': 'watch', 'ident': ident},
    complete: function (req, status) {
      if (status == 'success') {
        $('div.watch').fadeOut ('fast', function () { $('div.watch').remove () });
      } else {
        $('div.watch').empty().append ($(req.responseText))
      }
    }
  });
}
