$(document).ready(function () {
    $('.textfield, .textarea').keydown(function (e) {
        let text_length = $(e.target).prop('value').length;
        let min_length = parseInt($(e.target).attr('minlength'));
        let max_length = parseInt($(e.target).attr('maxlength'));
        $(e.target).next('span').text(text_length);
        if (text_length < min_length || text_length > max_length)
            $(e.target).next('span').addClass('counter__red');
        else
            $(e.target).next('span').removeClass('counter__red');
    })
});