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

    chart = $.plot($(".flot-chart-content"), series, {
        grid: {
            borderWidth: 0
        },
        shadowSize: 0,
        yaxis: {tickLength:0, tickDecimals: 0, min: 0}, 
        xaxis: {tickLength:0, mode: "time", min: new Date().getTime(), tickSize: [1, 'minute']},
        legend: {position: 'nw', labelBoxBorderColor: null}
    });

    function weird(data, new_thing, now) {
        if (data.length) {
            data.shift();
        }
        while (data.length < maximum) {
            data.push([now, new_thing]);
        }
        return data;
    }

    setInterval(function updateStats() {
        $.getJSON('/api/v1/bind_stats').done(function(data) {
            var now = new Date().getTime();
            series[0].data = weird(success, data.success, now);
            series[1].data = weird(failure, data.failure, now);
            series[2].data = weird(dropped, data.dropped, now);
            series[3].data = weird(duplicate, data.duplicate, now);
            series[4].data = weird(referral, data.referral, now);
            series[5].data = weird(recursion, data.recursion, now);
            series[6].data = weird(nxdomain, data.nxdomain, now);
            series[7].data = weird(nxrrset, data.nxrrset, now);
            chart.setData(series);
            chart.setupGrid();
            chart.draw();
        });
    }, 10000);
});
