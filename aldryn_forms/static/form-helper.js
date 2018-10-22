$(document).ready(function () {
    $('.textfield').on('input', count_input);
    if ($('.dateinput').length > 0) {
        $('.dateinput').datepicker({
            changeMonth: true,
            changeYear: true,
            yearRange: "1850:2050",
            dateFormat: 'dd.mm.yy',
            beforeShow: function (el, dp) {
                $(el).parent().append($('#ui-datepicker-div'));
                $('#ui-datepicker-div').hide();
            },
        });
    }
});

function count_input(e) {
    let elm = e.target ? e.target : e;
    let text = $(elm).prop('value');
    let text_length = text ? text.length : 0;
    let min_length = parseInt($(elm).attr('minlength'));
    let max_length = parseInt($(elm).attr('maxlength'));

    if (min_length || max_length){
        if (text_length == 0){
            $(elm).next('span').text("");
        } else {
            $(elm).next('span').text(text_length);
        }

        if ((min_length && text_length < min_length) || (max_length && text_length > max_length))
            $(elm).next('span').addClass('counter__red');
        else
            $(elm).next('span').removeClass('counter__red');
    }
}

