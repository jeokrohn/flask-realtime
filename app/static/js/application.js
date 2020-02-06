"use strict"
$(document).ready(function(){
    let socket=io.connect();

    socket.on("output", function(msg){
        // console.log("Received new line: " + msg.data);
        let log = document.getElementById("log");
        let e = $('#log')
        e.append(msg.data + '<br>');
        e.scrollTop(log.scrollHeight);
    });

    $('button#start-space-stats').on('click', function(event){
        $('#log').empty();
        socket.emit('start_space_stats');
    });

    $('button#start-create-spaces').on('click', function(event){
        $('#log').empty();
        socket.emit('start_create_spaces');
    });

    $('button#start-delete-spaces').on('click', function(event){
        $('#log').empty();
        socket.emit('start_delete_spaces');
    });


    $('button#stop').on('click', function(event){
        socket.emit('stop_request');
    });

    $('button#clear').on('click', function(event){
        $('#log').empty();
    });

});