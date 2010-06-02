(function(QU){

    var module = null;
    var test = null;
    var ws = new WebSocket('ws://' + window.location.host + '/')
    QU.stop(100);
    ws.onopen = function() {
        QU.start();
    };

    QU.moduleStart = function(name){
        module = name;
//        name = name.replace(/ /g, '_')
//        var url = ['ws://', window.location.host, '/', name, '/'].join('');
//        var this_ws = new WebSocket(url);
//        QU.stop(100);
//        this_ws.onopen = function() {
//            QU.start();
//        };
//        ws[module] = this_ws


    };
//    QU.moduleDone = function(name, failures, total){
//        var this_ws = ws[name]
//        if (this_ws){
//            console.log('Closing ' + name)
//            this_ws.close();
//        }
//        else {
//            console.log('No websocket for ' + name)
//        }
//    }
    QU.testStart = function(name){
        test = name;
    };
//    QU.log = function(result, message){
//        var this_ws = ws[module];
//        var this_test = test ? test.replace(/ /g, '_'): 'None'
//        var name = [module.replace(/ /g, '_'), this_test, message].join('.')
//        var payload = JSON.stringify({name: name, result: result});
//        this_ws.send(payload);
//    }
    QU.testDone = function(name, failures, total){
        var payload = JSON.stringify({namespace: module,
                                      name: name,
                                      failures: failures,
                                      total: total});
        ws.send(payload);

    };
    QU.done = function(failures, total){
        console.log(JSON.stringify({DONE: {failed: failures, total: total}}));
        ws.send(JSON.stringify({DONE: {failed: failures, total: total}}));
        //ws.close();
    };
}(QUnit))