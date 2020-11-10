

function set_fig(data, view_data) {
    let y_range;
    switch(view_data.show) {
        case "am":
            y_range = [12 * 4, 24 * 4]
            break;
        case "pm":
            y_range = [0, 12 * 4]
            break;
        case "peak":
            y_range = [4, 9 * 4]
            break;
        default:
            y_range = [0, 24 * 4]
    }

    let BOOTSTRAP_BLUE = 'rgb(2, 117, 216)'
    let BOOTSTRAP_GREEN = 'rgb(92, 184, 92)'
    let BOOTSTRAP_LIGHT_BLUE = 'rgb(91, 192, 222)'
    let BOOTSTRAP_YELLOW = 'rgb(240, 226, 78)'
    let BOOTSTRAP_ORANGE = 'rgb(240, 173, 78)'
    let BOOTSTRAP_RED = 'rgb(217, 83, 79)'

    let text_scatter_x = []
    let text_scatter_y = []
    let text_scatter_text = []
    if(view_data.show_text) {
        for (let i = y_range[0]; i < y_range[1]; i++) {
            for (let j = 0; j < data.x.length; j++) {
                if (data.z[i][j] !== -4.5 && data.z[i][j] < data.max) {
                    text_scatter_x.push(data.x[j])
                    text_scatter_y.push(data.y[i])
                    text_scatter_text.push(String(data.max - data.hover[i][j]))
                }
            }
        }
    }

    let l = data.max + 5;
    let k = {
        data: [
            {
                name: "",
                z: data.z,
                x: data.x,
                y: data.y,
                text: data.hover,
                hovertemplate: "%{y}: %{text}/" + data.max,
                showscale: false,
                hoverongaps: false,
                zmin: -5,
                zmax: data.max,
                xgap: 5,
                ygap: 0.1,
                type: 'heatmap',
                colorscale: [
                    [0.0, 'rgb(192,192,192)'], [1.0/l, 'rgb(192,192,192)'],
                    [1.0/l, BOOTSTRAP_LIGHT_BLUE], [2.0/l, BOOTSTRAP_LIGHT_BLUE],
                    [2.0/l, BOOTSTRAP_GREEN], [5.0/l, BOOTSTRAP_GREEN],
                    [5.0/l, BOOTSTRAP_BLUE], [(l - 4)/l, BOOTSTRAP_BLUE],
                    [(l - 3)/l, BOOTSTRAP_YELLOW], [(l-2)/l, BOOTSTRAP_YELLOW],
                    [(l-1)/l, BOOTSTRAP_ORANGE], [0.99, BOOTSTRAP_ORANGE],
                    [0.99, BOOTSTRAP_RED], [1.0, BOOTSTRAP_RED]
                ]
            },
            {
                name:"",
                x: text_scatter_x,
                y: text_scatter_y,
                text: text_scatter_text,
                type: "scatter",
                mode:"text",
                hoverinfo:'skip',
                textfont: {
                    color: 'rgb(0,0,0)'
                },
            }
        ],
        layout: {
            margin: {t:40, r:0, l:40, b:0},
            padding: {t:0, r:0, l:0, b:0},
             yaxis: {
                 fixedrange: true,
                 range: y_range.map(x => x -0.5),
                 tickmode: 'linear',
                 tick0: 7,
                 dtick: 4,
                 ticklen:0
             },
             xaxis: {
                 mirror: "allticks",
                 side: "top",
                 fixedrange: true,
                 tickformat: '%a\n%d/%m',
                 dtick: data.x[1] - data.x[0],
                 tick0: data.x[0],
                 ticklen:0
             }
         }
    }
    return [k]
}

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        set_fig: set_fig
    }
});