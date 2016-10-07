/**
 * Code for persistent (floating) table headers
 * From Chris Coyier
 * https://css-tricks.com/persistent-headers/
 *
 * "Use as you will" license
 */
function UpdateTableHeaders() {
   $(".persist-area").each(function() {
   
       var el             = $(this),
           offset         = el.offset(),
           scrollTop      = $(window).scrollTop(),
           floatingHeader = $(".floatingHeader", this)
       
       if ((scrollTop > offset.top) && (scrollTop < offset.top + el.height())) {
           floatingHeader.css({
            "visibility": "visible"
           });
       } else {
           floatingHeader.css({
            "visibility": "hidden"
           });      
       };
   });
}


// DOM Ready      
$(function() {
  var floatingHeader;

  	$(".persist-area").each(function(){

  		floatingHeader = $(".persist-header", this);
		
  		floatingHeader.before(floatingHeader.clone());
	
  		floatingHeader.children().css("width", function(i, val){
  			return $(floatingHeader).children().eq(i).css("width", val);
  		});
	
  		floatingHeader.addClass("floatingHeader");
		
  	});
/*
   var clonedHeaderRow;

   $(".persist-area").each(function() {
       clonedHeaderRow = $(".persist-header", this);
       clonedHeaderRow
         .before(clonedHeaderRow.clone())
         .css("width", clonedHeaderRow.width())
         .addClass("floatingHeader");
         
   });
  */ 
   $(window)
    .scroll(UpdateTableHeaders)
    .trigger("scroll");
   
});