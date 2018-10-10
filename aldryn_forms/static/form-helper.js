$(document).ready(function () {
    $('.textfield').keydown(function (e) {
        let text_length = $(e.target).prop('value').length;
        let min_length = parseInt($(e.target).attr('minlength'));
        let max_length = parseInt($(e.target).attr('maxlength'));
        $(e.target).next('span').text(text_length);
        if (text_length < min_length || text_length > max_length)
            $(e.target).next('span').addClass('counter__red');
        else
            $(e.target).next('span').removeClass('counter__red');
    });

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