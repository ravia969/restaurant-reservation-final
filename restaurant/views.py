from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from .models import Guest, Manager, Table, MenuItem, Restaurant, Visit, Reservation, Friendship, ReservedTables
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from datetime import datetime as dt
import datetime
import pytz
from django.db import transaction


# Homepage
def index(request):
    return render(request, 'restaurant/index.html')


# User login
def login(request):
    if request.method == 'POST':
        # collecting form data
        username = request.POST.get('username')
        password = request.POST.get('password')
        # checking for user first
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                # check if it is quest or manager
                # search for guest
                guest = Guest.objects.all()
                for g in guest:
                    if g.user == user:
                        auth_login(request, user)
                        return HttpResponseRedirect(reverse('restaurant:guest', args=(g.id,)))
                # search for manager
                managers = Manager.objects.all()
                for m in managers:
                    if m.user == user:
                        auth_login(request, user)
                        return HttpResponseRedirect(reverse('restaurant:manager', args=(m.id,)))
            else:
                return render(request, 'restaurant/index.html', {
                    'error_message': "Account is not activated!"
                })
        else:
            return render(request, 'restaurant/index.html', {
                'error_message': "Wrong Email address or Password!"
            })


# User logout
def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse('restaurant:index'))


# User register form
def register(request):
    return render(request, 'restaurant/register.html')


def registration(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        # check password equality
        if password1 == password2:
            users = User.objects.all()
            for u in users:
                if u.username == username:
                    return render(request, 'restaurant/register.html', context={
                        'error_message': "User already exists!"
                    })
            # user does not exist, create new
            new_user = User.objects.create_user(username, username, password1)
            new_user.is_staff = False
            new_user.is_active = False
            new_user.is_superuser = False
            new_user.save()
            # create activation link
            new_user_id = str(new_user.id)
            link = "http://127.0.0.1:8000/restaurant/activation/"+new_user_id+"/"
            message_text = "Click on the following link to complete your registration\n\n" + link
            # sending email
            send_mail('Restaurant - Profile Activation', message_text, 'ravi.arora1149@gmail.com', [new_user.username],
                      fail_silently=False)
            # creating guest object
            new_guest = Guest.objects.create(user=new_user)
            new_user.save()
            print("Successful! Guest inserted: " + str(new_guest))

            # back on page
            return render(request, 'restaurant/register.html', context={
                'info_message': "Account created successfully. Email with activation link was sent!"
            })
        else:
            return render(request, 'restaurant/register.html', context={
                'error_message': "Password wasn't repeated correctly!"
            })


# User activation
def activation(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user is not None:
        user.is_active = True
        user.save()
        return render(request, 'restaurant/index.html', context={
            'info_message': "Account successfully activated!"
        })
    else:
        return render(request, 'restaurant/index.html', context={
            'error_message': "Error with activation link!"
        })


"""Manager pages"""

# Manager's default page
@login_required(login_url='/')
def manager(request, manager_id):
    this_manager = get_object_or_404(Manager, pk=manager_id)
    restaurant = this_manager.restaurant
    restaurant_tables = Table.objects.filter(restaurant=restaurant)
    rows = range(1, restaurant.rows+1)
    cols = range(1, restaurant.columns+1)
    return render(request, 'restaurant/manager.html', {
        'manager': this_manager,
        'restaurant': restaurant,
        'tables': restaurant_tables,
        'rows': rows,
        'columns': cols
    })


# Manager's profile page
@login_required(login_url='/')
def profiling(request, manager_id):
    this_manager = get_object_or_404(Manager, pk=manager_id)
    return render(request, 'restaurant/manager_profile.html', {
        'manager': this_manager
    })


# Update Manager's profile
@login_required(login_url='/')
def updating(request, manager_id):
    this_manager = get_object_or_404(Manager, pk=manager_id)
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 == password2:
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            updated_manager = Manager.objects.get(pk=manager_id)
            # update profile
            updated_user = updated_manager.user
            updated_user.first_name = first_name
            updated_user.last_name = last_name
            updated_user.save()
            # update password if changed
            if password1 != '':
                updated_user.set_password(password1)
                updated_user.save()
            print("Success! Updated Manager: " + str(updated_manager))
            return HttpResponseRedirect(reverse('restaurant:profiling', args=(manager_id, )))
        else:
            return render(request, 'restaurant/manager_profile.html', context={
                'manager': this_manager,
                'error_message': "New password wasn't repeated correctly!"
            })


# Manager's page for menu setting
@login_required(login_url='/')
def menu(request, restaurant_id, manager_id):
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    menu_items = MenuItem.objects.filter(restaurant=this_restaurant)
    this_manager = Manager.objects.get(pk=manager_id)
    return render(request, 'restaurant/menu.html', {
        'manager': this_manager,
        'restaurant': this_restaurant,
        'menu': menu_items
    })


# Deleting menu item from restaurant
@login_required(login_url='/')
def remove(request, item_id, restaurant_id, manager_id):
    item = get_object_or_404(MenuItem, pk=item_id)
    item.delete()
    return HttpResponseRedirect(reverse('restaurant:menu', args=(restaurant_id, manager_id,)))


# Insert menu item for restaurant
@login_required(login_url='/')
def insert(request, restaurant_id, manager_id):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = float(request.POST.get('price'))
        this_restaurant = Restaurant.objects.get(pk=restaurant_id)

        mi = MenuItem.objects.create(name=name, description=description, price=price, restaurant=this_restaurant)
        mi.save()
        print("Success. Inserted MenuItem: " + str(mi))

        return HttpResponseRedirect(reverse('restaurant:menu', args=(restaurant_id, manager_id,)))


# show edit menu item for restaurant
@login_required(login_url='/')
def edit(request, item_id, restaurant_id, manager_id):
    this_item = get_object_or_404(MenuItem, pk=item_id)
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    this_manager = get_object_or_404(Manager, pk=manager_id)
    menu_items = MenuItem.objects.filter(restaurant=this_restaurant)
    return render(request, 'restaurant/menuedit.html', context={
        'manager': this_manager,
        'restaurant': this_restaurant,
        'menu': menu_items,
        'edition': this_item
    })

# save edited data
@login_required(login_url='')
def saveedition(request, item_id, restaurant_id, manager_id):
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    this_manager = get_object_or_404(Manager, pk=manager_id)
    this_item = get_object_or_404(MenuItem, pk=item_id)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = float(request.POST.get('price'))
        edit_item = MenuItem.objects.get(pk=item_id)
        edit_item.name = name
        edit_item.description = description
        edit_item.price = price
        edit_item.save()
        print("Success! Edited MenuItem: " + str(edit_item))
        return HttpResponseRedirect(reverse('restaurant:menu', args=(restaurant_id, manager_id, )))


# class for sitting schedule setting
class Place:
    def __init__(self, row, column, name):
        self.row = row
        self.column = column
        self.name = name


# Setting sitting schedule
@login_required(login_url='/')
def tables(request, restaurant_id, manager_id):
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    if this_restaurant.is_ready:
        return HttpResponseRedirect(reverse('restaurant:manager', args=(manager_id,)))
    else:
        rows = range(1, this_restaurant.rows+1)
        cols = range(1, this_restaurant.columns+1)
        places = []
        for i in rows:
            for j in cols:
                name = (i-1)*this_restaurant.columns + j
                places.append(Place(i, j, name))
        max_tables = this_restaurant.tables
        this_manager = Manager.objects.get(pk=manager_id)
        return render(request, 'restaurant/tables.html', {
            'manager': this_manager,
            'restaurant': this_restaurant,
            'rows': rows,
            'columns': cols,
            'tables': max_tables,
            'places': places
        })


# Setup table schedule
@login_required(login_url='/')
def setup(request, restaurant_id, manager_id):
    # prepare data for going back
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    this_manager = get_object_or_404(Manager, pk=manager_id)
    r_rows = range(1, this_restaurant.rows+1)
    r_cols = range(1, this_restaurant.columns+1)
    r_places = []
    for i in r_rows:
        for j in r_cols:
            r_name = (i-1)*this_restaurant.columns + j
            r_places.append(Place(i, j, r_name))

    if this_restaurant.is_ready:
        return HttpResponseRedirect(reverse('restaurant:manager', args=(manager_id,)))
    else:
        rows = range(1, this_restaurant.rows+1)
        cols = range(1, this_restaurant.columns+1)
        places = range(1, this_restaurant.tables+1)
        tables_order = []
        tables_numbers = []
        if request.method == 'POST':
            for p in r_places:
                table_name = request.POST.get(str(p.name))
                # if inserted
                if table_name != '':
                    table_num = int(table_name)
                    # check for repeat
                    if table_num in tables_numbers:
                        message = "Please set " + str(this_restaurant.tables) + " different tables!"
                        return render(request, 'restaurant/tables.html', {
                            'manager': this_manager,
                            'restaurant': this_restaurant,
                            'rows': r_rows,
                            'columns': r_cols,
                            'tables': this_restaurant.tables,
                            'places': r_places,
                            'error_message': message
                        })
                    else:
                        r = p.row
                        c = p.column
                        tables_order.append(Place(r, c, table_num))
                        tables_numbers.append(table_num)
            # check for number of tables
            if len(tables_order) == this_restaurant.tables:
                # before inserting tables, see for duplicates

                # inserting tables
                for t in range(0, len(tables_order)):
                    r = tables_order[t].row
                    c = tables_order[t].column
                    n = tables_order[t].name
                    # inserting table
                    new_table = Table.objects.create(number=n, row=r, column=c, currently_free=True,
                                                     restaurant=this_restaurant)
                    new_table.save()
                    print("Success. Inserted Table: " + str(new_table))
                # restaurant is now ready
                update_restaurant = Restaurant.objects.get(pk=restaurant_id)
                update_restaurant.is_ready = True
                update_restaurant.save()
                print("Success. Updated Restaurant: " + str(update_restaurant))
                return HttpResponseRedirect(reverse('restaurant:manager', args=(manager_id,)))
            else:
                message = "Please set " + str(this_restaurant.tables) + " tables!"
                return render(request, 'restaurant/tables.html', {
                    'manager': this_manager,
                    'restaurant': this_restaurant,
                    'rows': r_rows,
                    'columns': r_cols,
                    'tables': this_restaurant.tables,
                    'places': r_places,
                    'error_message': message
                })


"""User pages"""

# Guest's default page
@login_required(login_url='/')
def guest(request, guest_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    right_now = timezone.now()
    visits = Visit.objects.filter(guest=this_guest).filter(confirmed=True).filter(ending_time__lte=right_now)
    return render(request, 'restaurant/guest.html', context={
        'guest': this_guest,
        'visits': visits
    })


# Rating visit view
@login_required(login_url='/')
def rate(request, guest_id, visit_id):
    this_visit = get_object_or_404(Visit, pk=visit_id)
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_reservation = this_visit.reservation
    # searching for friends visits
    friends_visits = Visit.objects.filter(reservation=this_reservation).filter(confirmed=True).exclude(guest=this_guest)
    count = len(friends_visits)
    # show page
    return render(request, 'restaurant/rating.html', context={
        'guest': this_guest,
        'visit': this_visit,
        'friends': friends_visits,
        'count': count
    })

# Process rate
@login_required(login_url='/')
def rating(request, guest_id, visit_id):
    if request.method == 'POST':
        this_rating = int(request.POST.get('rating'))
        this_visit = Visit.objects.get(pk=visit_id)
        this_visit.grade = this_rating
        this_visit.save()
        print("Success! Rated: " + str(this_visit))
        return HttpResponseRedirect(reverse('restaurant:guest', args=(guest_id, )))





# Display restaurant list with ratings
@login_required(login_url='/')
def restaurantlist(request, guest_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    restaurants = Restaurant.objects.filter(is_ready=True)
    restaurant_rate = []
    restaurant_friend_rate = []
    for r in restaurants:
        restaurant_rate.append(get_restaurant_rating(r))
        restaurant_friend_rate.append(get_restaurants_friends_rating(r, this_guest))
    restaurants_send = zip(restaurants, restaurant_rate, restaurant_friend_rate)
    return render(request, 'restaurant/restaurants_list.html', context={
        'guest': this_guest,
        'restaurants': restaurants_send
    })


# calculates restaurant's rating
def get_restaurant_rating(this_restaurant):
    list_of_visits = Visit.objects.filter(confirmed=True)
    s = 0
    c = 0
    for v in list_of_visits:
        if v.reservation.restaurant == this_restaurant:
            if v.grade is not None and v.grade >= 1:
                s += v.grade
                c += 1
    if c == 0:
        return 0
    else:
        r = s/c
        return round(r, 2)




# shows restaurant's profile with menu
@login_required(login_url='/')
def restaurantmenu(request, guest_id, restaurant_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    menu_items = MenuItem.objects.filter(restaurant=this_restaurant)
    return render(request, 'restaurant/restaurant_menu.html', context={
        'restaurant': this_restaurant,
        'guest': this_guest,
        'items': menu_items
    })




# reservation time
@login_required(login_url='/')
def reservationtime(request, guest_id, restaurant_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    return render(request, 'restaurant/reservation_time.html', context={
        'guest': this_guest,
        'restaurant': this_restaurant
    })





# reserving tables
@login_required(login_url='/')
@transaction.atomic
def reservetables(request, guest_id, restaurant_id, reservation_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    this_reservation = get_object_or_404(Reservation, pk=reservation_id)
    this_tables = Table.objects.filter(restaurant=this_restaurant)
    selected_tables = []
    if request.method == 'POST':
        for t in this_tables:
            if request.POST.get(str(t.id)):
                selected_tables.append(t)
        if len(selected_tables) == 0:
            delete_reservation = Reservation.objects.get(pk=reservation_id)
            delete_reservation.delete()
            print("Deleted Reservation!!!")
            return render(request, 'restaurant/reservation_time.html', context={
                'guest': this_guest,
                'restaurant': this_restaurant,
                'error_message': "Unsuccessful Reservation! Tables weren't selected!"
            })
        # try to reserve tables
        try:
            with transaction.atomic():
                for t in selected_tables:
                    reserve_new_table = ReservedTables.objects.create(reservation=this_reservation, table=t)
                    reserve_new_table.save()
                    print("Success! Reserved table: " + str(t))
        # someonte reserve the table meanwhile
        except:
            delete_reservation = Reservation.objects.get(pk=reservation_id)
            delete_reservation.delete()
            print("Deleted Reservation!!!")
            return render(request, 'restaurant/reservation_time.html', context={
                'guest': this_guest,
                'restaurant': this_restaurant,
                'error_message': "Unsuccessful Reservation! Selected tables are already reserved!"
            })

        # if everything was fine create new visit object
        stops = this_reservation.get_finishing_time()
        new_visit = Visit.objects.create(ending_time=stops, confirmed=True, reservation=this_reservation, guest=this_guest)
        new_visit.save()
        print("Success! Created new visit: " + str(new_visit))
        list_of_friends = get_friends_list(this_guest)
        return render(request, 'restaurant/reservation_friends.html', context={
            'guest': this_guest,
            'restaurant': this_restaurant,
            'reservation': this_reservation,
            'friends': list_of_friends
        })



@login_required(login_url='')
def invitefriends(request, guest_id, restaurant_id, reservation_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
    this_reservation = get_object_or_404(Reservation, pk=reservation_id)
    # get friends list
    friend_list = get_friends_list(this_guest)
    selected_friends = []
    if request.method == 'POST':
        # collect friends
        for f in friend_list:
            if request.POST.get(str(f.id)):
                selected_friends.append(f)
        # if there is no selected friends, send to my reservations
        if len(selected_friends) == 0:
            return HttpResponseRedirect(reverse('restaurant:myreservations', args=(guest_id, )))
        else:
            # send mail invitations and create visit objects
            stops = this_reservation.get_finishing_time()
            for this_friend in selected_friends:
                print("Working for: " + str(this_friend))
                friend_guest = get_object_or_404(Guest, pk=this_friend.id)
                new_visit = Visit.objects.create(ending_time=stops, confirmed=False, reservation=this_reservation,
                                                 guest=friend_guest)
                new_visit.save()
                print("Success! Created new visit: " + str(new_visit))
                # send_mail
                message_text = "You got an invitation to visit Restaurant. Login and follow link to see more:\n\n"
                link_text = "http://127.0.0.1:8000/restaurant/showinvitation/"+str(friend_guest.id)+"/"+reservation_id+"/"+str(new_visit.id)+"/"
                text_to_send = message_text + link_text
                send_mail('Restaurant - Invitation', text_to_send, 'ravi.arora1149@gmail.com', [friend_guest.user.username],
                          fail_silently=False)
                print("Success! Mail sent to: " + str(friend_guest))
            # all finished
            return HttpResponseRedirect(reverse('restaurant:myreservations', args=(guest_id, )))



@login_required(login_url='/')
def showinvitation(request, guest_id, reservation_id, visit_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_reservation = get_object_or_404(Reservation, pk=reservation_id)
    this_visit = get_object_or_404(Visit, pk=visit_id)
    right_now = timezone.now()
    if right_now > this_visit.ending_time:
        return render(request, 'restaurant/reservation_confirm.html', context={
            'guest': this_guest,
            'reservation': this_reservation,
            'visit': this_visit,
            'show': False,
            'error_message': "Time's up!"
        })
    else:
        if this_visit.confirmed:
            return render(request, 'restaurant/reservation_confirm.html', context={
                'guest': this_guest,
                'reservation': this_reservation,
                'visit': this_visit,
                'show': False,
                'info_message': "Invitation already confirmed!"
            })
        else:
            return render(request, 'restaurant/reservation_confirm.html', context={
                'guest': this_guest,
                'reservation': this_reservation,
                'visit': this_visit,
                'show': True
            })


@login_required(login_url='/')
def acceptinvitation(request, guest_id, reservation_id, visit_id):
    this_guest = get_object_or_404(Guest, pk=guest_id)
    this_reservation = get_object_or_404(Reservation, pk=reservation_id)
    this_visit = get_object_or_404(Visit, pk=visit_id)
    new_visit = Visit.objects.get(pk=visit_id)
    new_visit.confirmed = True
    new_visit.save()
    print("Success! Confirmed Visit: " + str(this_visit))
    return render(request, 'restaurant/reservation_confirm.html', context={
        'guest': this_guest,
        'reservation': this_reservation,
        'visit': this_visit,
        'info_message': "Invitation Accepted!"
    })