//Flot BIND stats chart
$(function() {
    var maximum = $(".flot-chart-content").outerWidth() / 2 || 300;
    var success = [];
    var failure = [];
    var dropped = [];
    var duplicate = [];
    var referral = [];
    var recursion = [];
    var nxdomain = [];
    var nxrrset = [];
    series = [{
        data: [],
        label: 'success',
        lines: {show:true}
    },{
        data: [],
        label: 'failure',
        lines: {show:true}
    },{
        data: [],
        label: 'dropped',
        lines: {show:true}
    },{
        data: [],
        label: 'duplicate',
        lines: {show:true}
    },{
        data: [],
        label: 'referral',
        lines: {show:true}
    },{
        data: [],
        label: 'recursion',
        lines: {show:true}
    },{
        data: [],
        label: 'nxdomain',
        lines: {show:true}
    },{
        data: [],
        label: 'nxrrset',
        lines: {show:true}
    }];

    chart = $.plot('.flot-chart-content', series, {});

    function weird(data, new_thing) {
        if (data.length) {
            data = data.slice(1);
        }
        while (data.length < maximum) {
            var previous = data.length ? data[data.length - 1] : 50;
            data.push(new_thing);
        }
        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]]);
        }

        return res;
    }

    setInterval(function updateStats() {
        $.getJSON('/api/v1/bind_stats').done(function(data) {
            series[0].data = weird(success, data.success);
            series[1].data = weird(failure, data.failure);
            series[2].data = weird(dropped, data.dropped);
            series[3].data = weird(duplicate, data.duplicate);
            series[4].data = weird(referral, data.referral);
            series[5].data = weird(recursion, data.recursion);
            series[6].data = weird(nxdomain, data.nxdomain);
            series[7].data = weird(nxrrset, data.nxrrset);
            chart.setData(series);
            chart.draw();

            // also do something with data.running!
            if (data.running) {
                $(".bind-status").children("a").children("i").attr('class', "fa fa-arrow-circle-up bind-up");
                $(".bind-status").children("a").children("i").attr('title', 'BIND is running');
            } else {
                $(".bind-status").children("a").children("i").attr('class', "fa fa-arrow-circle-down bind-down");
                $(".bind-status").children("a").children("i").attr('title', 'BIND is down');
            }
        })
    }, 10000);
});
