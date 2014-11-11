//Flot BIND stats chart
$(function() {
    var maximum = $(".flot-chart-content").outerWidth() / 2 || 300;
    var user = [];
    var failure = [];
    var dropped = [];
    var duplicate = [];
    var referral = [];
    var recursion = [];
    var nxdomain = [];
    var nxrrset = [];
    series = [{
        data: [],
        label: 'user',
        lines: {show:true}
    },{
        data: [],
        label: 'referral',
        lines: {show:true}
    },{
        data: [],
        label: 'nxrrset',
        lines: {show:true}
    },{
        data: [],
        label: 'nxdomain',
        lines: {show:true}
    },{
        data: [],
        label: 'recursion',
        lines: {show:true}
    },{
        data: [],
        label: 'failure',
        lines: {show:true}
    },{
        data: [],
        label: 'duplicate',
        lines: {show:true}
    },{
        data: [],
        label: 'dropped',
        lines: {show:true}
    }];

    chart = $.plot($(".flot-chart-content"), series, {
        grid: {
            borderWidth: 0
        },
        colors: ['#008000', '#0C64E8', '#E80C3E', '#FFA500', '#1CC8E8', '#E80C8C', '#00FF3F', '#FFFF00'],
        shadowSize: 0,
        yaxis: {tickLength:1, tickDecimals: 0, min: 0}, 
        xaxis: {tickLength:1, mode: "time", tickSize: [1, 'minute']},
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
            series[0].data = weird(user, data.user, now);
            series[1].data = weird(referral, data.referral, now);
            series[2].data = weird(nxrrset, data.nxrrset, now);
            series[3].data = weird(nxdomain, data.nxdomain, now);
            series[4].data = weird(recursion, data.recursion, now);
            series[5].data = weird(failure, data.failure, now);
            series[6].data = weird(duplicate, data.duplicate, now);
            series[7].data = weird(dropped, data.dropped, now);
            chart.setData(series);
            chart.setupGrid();
            chart.draw();
        });
    }, 10000);
});
