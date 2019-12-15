$(document).ready(function(){
    var socket=io.connect();
    var lines=[];
    var s='';

    socket.on("output", function(msg){
        console.log("Received new line: " + msg);
        // $('#log').append('<p>' + msg.data + '</p>');
        $('#log').append(msg.data + '<br>');
    });

    $('button#start').on('click', function(event){
        $('#log').empty();
        socket.emit('start_request');
    });

    $('button#stop').on('click', function(event){
        socket.emit('stop_request');
    });
});