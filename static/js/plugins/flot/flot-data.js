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
    }];

    chart = $.plot($(".flot-chart-content"), series, {
        grid: {
            borderWidth: 0
        },
        colors: ['#008000', '#0C64E8', '#E80C3E', '#FFA500', '#1CC8E8', '#E80C8C', '#00FF3F'],
        shadowSize: 0,
        yaxis: {tickLength:1, tickDecimals: 0, min: 0}, 
        xaxis: {tickLength:1 , mode: "time", tickSize: [15, 'minute']},
        legend: {position: 'nw', labelBoxBorderColor: null}
    });

    function weird() {
        $.getJSON('/api/v1/bind_stats').done(function(data) {
            for (var i = 0;i<data.length;i++) {
                data.successes[i][0] = new Date(data.successes[i][0]);
                data.referrals[i][0] = new Date(data.referrals[i][0]);
                data.nxrrset[i][0] = new Date(data.nxrrset[i][0]);
                data.nxdomain[i][0] = new Date(data.nxdomain[i][0]);
                data.recursions[i][0] = new Date(data.recursions[i][0]);
                data.failures[i][0] = new Date(data.failures[i][0]);
                data.duplicates[i][0] = new Date(data.duplicates[i][0]);
            }
            series[0].data = data.successes;
            series[1].data = data.referrals;
            series[2].data = data.nxrrset;
            series[3].data = data.nxdomain;
            series[4].data = data.recursions;
            series[5].data = data.failures;
            series[6].data = data.duplicates;
            chart.setData(series);
            chart.setupGrid();
            chart.draw();
        });
    }

    weird()

    setInterval(function updateStats() {
        weird();
    }, 30000);
});
